provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}

# Set the GCP project apis first. This needs to happen before creating a new instance.
resource "google_project_service" "cloud_resource_manager_api" {
  project            = var.project
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute" {
  project            = var.project
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute_api" {
  project            = var.project
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

# Static IP address for the deployment. We'll assign this to our HTTPS load balancer later.
resource "google_compute_address" "static_ip" {
  name       = "${var.project}-static-ip"
  region     = var.region
  depends_on = [google_project_service.compute_api]

  lifecycle {
    prevent_destroy = true
  }
}

# Next step is to set up our networking and an HTTPS load balancer.

# Start with a new VPC (VPN?) network
resource "google_compute_network" "vpn_network" {
  name                    = "${var.project}-vpn"
  auto_create_subnetworks = false
}

# Create a proxy-only subnet. This will be used by the HTTPS load balancer.
resource "google_compute_subnetwork" "proxy_only" {
  name          = "${var.project}-proxy-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpn_network.id
  purpose       = "REGIONAL_MANAGED_PROXY"
  role          = "ACTIVE"
}

# We need to add a router to allow outbound access to the public internet
resource "google_compute_router" "nat_router" {
  name    = "${var.project}-nat-router"
  region  = var.region
  network = google_compute_network.vpn_network.id
}

resource "google_compute_router_nat" "nat_config" {
  name                               = "${var.project}-cloud-nat"
  router                             = google_compute_router.nat_router.name
  region                             = google_compute_router.nat_router.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# Firewall settings.
# The IP ranges are for Google's internal network, these shouldn't change
resource "google_compute_firewall" "firewall" {
  name    = "${var.project}-firewall"
  network = google_compute_network.vpn_network.name
  allow {
    protocol = "tcp"
    ports    = ["80", "443", "22", "3389",]
  }
  source_ranges = ["0.0.0.0/0", "35.235.240.0/20" /*required for ssh*/, "130.211.0.0/22", "35.191.0.0/16"]
  depends_on    = [google_project_service.compute_api]

  target_tags = ["http-server", "https-server"]

  priority = 65534
}

# Create a separate private subnet. This will be used by the compute instance later.
resource "google_compute_subnetwork" "private_subnet" {
  name          = "${var.project}-subnet"
  ip_cidr_range = "10.10.0.0/24"
  region        = var.region
  network       = google_compute_network.vpn_network.id
  purpose       = "PRIVATE" # default; can omit
}

resource "google_compute_health_check" "tcp_check" {
  name                = "tcp-health-check"
  check_interval_sec  = 5
  timeout_sec         = 5
  healthy_threshold   = 2
  unhealthy_threshold = 10

  tcp_health_check {
    port = 80
  }
}

# Create the compute instance
resource "google_compute_instance" "server" {
  name                      = var.vm_name
  project                   = var.project
  machine_type              = var.machine_type
  zone                      = var.zone
  tags                      = ["${var.project}-server", "webserver-fw", "allow-ssh-iap", "http-server", "https-server"]
  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = "ubuntu-2204-lts"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.private_subnet.name
  }

  service_account {
    email  = var.service_account_email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata_startup_script = file(var.script_path)

  depends_on = [google_project_service.cloud_resource_manager_api, google_project_service.compute_api, google_compute_firewall.firewall, google_compute_network.vpn_network, google_compute_router_nat.nat_config, google_compute_router.nat_router]
}

# Next we need to set up the HTTPS load balancer. There are several steps to this.

# Create an unmanaged instance group
resource "google_compute_instance_group" "instance_group" {
  name = "${var.project}-instance-group"
  zone = var.zone

  instances = [
    google_compute_instance.server.self_link
  ]

  network = google_compute_network.vpn_network.id

  named_port {
    name = "port-redirection"
    port = 80
  }
}

# Create a backend service
resource "google_compute_backend_service" "https_backend" {
  name                  = "${var.project}-backend"
  protocol              = "HTTP"
  port_name             = "port-redirection"
  timeout_sec           = 10
  health_checks         = [google_compute_health_check.tcp_check.self_link]
  load_balancing_scheme = "EXTERNAL"

  backend {
    group = google_compute_instance_group.instance_group.self_link
  }
}

# At this point, we're ready to set up a HTTPS load balancer.
resource "google_compute_url_map" "default" {
  name            = "https-url-map"
  default_service = google_compute_backend_service.https_backend.self_link
}

resource "google_compute_managed_ssl_certificate" "lb_default" {
  provider = google-beta
  name     = "myservice-ssl-cert"

  managed {
    domains = ["platform.vectorinstitute.ai"]
  }
}

resource "google_compute_target_https_proxy" "default" {
  name             = "${var.project}-https-proxy"
  url_map          = google_compute_url_map.default.id
  ssl_certificates = [google_compute_managed_ssl_certificate.lb_default.id]
}

resource "google_compute_global_address" "default" {
  name = "${var.project}-https-lb-ip"
}

resource "google_compute_global_forwarding_rule" "default" {
  name                  = "${var.project}-https-forwarding-rule"
  ip_address            = google_compute_global_address.default.address
  port_range            = "443"
  target                = google_compute_target_https_proxy.default.self_link
  load_balancing_scheme = "EXTERNAL"
}
