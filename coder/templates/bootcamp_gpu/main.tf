terraform {
  required_providers {
    coder = {
      source = "coder/coder"
    }
    google = {
      source = "hashicorp/google"
    }
  }
}

provider "coder" {}

provider "google" {
  zone    = var.zone
  project = var.project
}

data "google_compute_default_service_account" "default" {}

data "coder_provisioner" "me" {}
data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}


data "coder_external_auth" "github" {
   id = var.github_app_id
}

locals {
  # Ensure Coder username is a valid Linux username
  username = "coder"
  repo_name = replace(regex(".*/(.*)", var.github_repo)[0], ".git", "")
}

resource "coder_agent" "main" {
  auth           = "google-instance-identity"
  arch           = "amd64"
  os             = "linux"
  startup_script = <<-EOT
    #!/bin/bash
    set -e

    export PATH="/home/${local.username}/.local/bin:$PATH"

    echo "Changing permissions of /home/${local.username} folder"
    sudo chown -R ${local.username}:${local.username} /home/${local.username}

    # Clone the GitHub repository
    cd "/home/${local.username}"

    if [ ! -d "${local.repo_name}" ] ; then
      git clone ${var.github_repo}
      cd ${local.repo_name}
      git checkout ${var.github_branch}
    else
      cd ${local.repo_name}
    fi

    echo "Running project startup script"

    if [ -f "scripts/setup.sh" ] ; then
      bash scripts/setup.sh
    else
      echo "No init script"
    fi

    echo "Startup script ran successfully!"

  EOT

  env = {
			GIT_AUTHOR_NAME     = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
			GIT_AUTHOR_EMAIL    = "${data.coder_workspace_owner.me.email}"
			GIT_COMMITTER_NAME  = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
			GIT_COMMITTER_EMAIL = "${data.coder_workspace_owner.me.email}"
	}

	metadata {
			display_name = "CPU Usage"
			key          = "0_cpu_usage"
			script       = "coder stat cpu"
			interval     = 10
			timeout      = 1
	}

	metadata {
			display_name = "RAM Usage"
			key          = "1_ram_usage"
			script       = "coder stat mem"
			interval     = 10
			timeout      = 1
	}
}

module "github-upload-public-key" {
  count            = data.coder_workspace.me.start_count
  source           = "registry.coder.com/coder/github-upload-public-key/coder"
  version          = "1.0.15"
  agent_id         = coder_agent.main.id
  external_auth_id = data.coder_external_auth.github.id
}

# See https://registry.terraform.io/modules/terraform-google-modules/container-vm
# Updated container module configuration for GPU access
module "gce-container" {
  source  = "terraform-google-modules/container-vm/google"
  version = "3.0.0"

  container = {
    image   = var.container_image
    command = ["sh"]
    args    = ["-c", coder_agent.main.init_script]
    securityContext = {
      privileged : true
    }
    # GPU-related environment variables
    env = [
      {
        name  = "PATH"
        value = "/usr/local/nvidia/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin"
      },
      {
        name  = "LD_LIBRARY_PATH"
        value = "/usr/local/nvidia/lib64:/usr/local/cuda/lib64"
      },
      {
        name  = "NVIDIA_VISIBLE_DEVICES"
        value = "all"
      },
      {
        name  = "NVIDIA_DRIVER_CAPABILITIES"
        value = "all"
      }
    ]
    # Declare volumes to be mounted
    volumeMounts = [
      {
        mountPath = "/cache"
        name      = "tempfs-0"
        readOnly  = false
      },
      {
        mountPath = "/home/${local.username}"
        name      = "data-disk-0"
        readOnly  = false
      },
      # GPU driver volumes
      {
        mountPath = "/usr/local/nvidia/lib64"
        name      = "nvidia-lib64"
        readOnly  = true
      },
      {
        mountPath = "/usr/local/nvidia/bin"
        name      = "nvidia-bin"
        readOnly  = true
      }
    ]
  }

  # Declare the volumes
  volumes = [
    {
      name = "tempfs-0"
      emptyDir = {
        medium = "Memory"
      }
    },
    {
      name = "data-disk-0"
      gcePersistentDisk = {
        pdName = "data-disk-0"
        fsType = "ext4"
      }
    },
    {
      name = "nvidia-lib64"
      hostPath = {
        path = "/var/lib/nvidia/lib64"
      }
    },
    {
      name = "nvidia-bin"
      hostPath = {
        path = "/var/lib/nvidia/bin"
      }
    }
  ]
}

resource "google_compute_disk" "pd" {
  project = var.project
  name    = "coder-${data.coder_workspace.me.id}-data-disk"
  type    = "pd-ssd"
  zone    = var.zone
  size    = var.pd_size
}

resource "google_compute_instance" "dev" {
  zone         = var.zone
  count        = data.coder_workspace.me.start_count
  name         = "coder-${lower(data.coder_workspace_owner.me.name)}-${lower(data.coder_workspace.me.name)}"

  # Use N1 machine type for T4 GPU compatibility
  machine_type = var.machine_type # Should be n1-standard-* for T4 GPUs

  # GPU configuration for T4
  guest_accelerator {
    type  = var.guest_accelerator_type
    count = 1
  }

  # Required for GPU instances
  scheduling {
    on_host_maintenance = "TERMINATE"
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  boot_disk {
    initialize_params {
      # Use Container-Optimized OS with GPU support (milestone 85+)
      image = "cos-cloud/cos-stable"
      size  = 50 # Increased size for GPU drivers
    }
  }

  attached_disk {
    source      = google_compute_disk.pd.self_link
    device_name = "data-disk-0"
    mode        = "READ_WRITE"
  }

  service_account {
    email = data.google_compute_default_service_account.default.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
      "https://www.googleapis.com/auth/devstorage.read_only" # Required for cos-extensions
    ]
  }

  metadata = {
    "gce-container-declaration" = module.gce-container.metadata_value
    # Add startup script to install GPU drivers
    "startup-script" = <<-EOF
      #!/bin/bash
      # Install GPU drivers
      sudo cos-extensions install gpu

      # Make drivers executable (required for COS)
      sudo mount --bind /var/lib/nvidia /var/lib/nvidia
      sudo mount -o remount,exec /var/lib/nvidia

      # Restart docker to pick up GPU runtime
      sudo systemctl restart docker
    EOF
  }

  labels = {
    container-vm = module.gce-container.vm_container_label
    gpu-type     = "nvidia-tesla-t4"
  }

  # Add network tags if you need specific firewall rules
  tags = ["gpu-instance", "coder-workspace"]
}

resource "coder_agent_instance" "dev" {
  count       = data.coder_workspace.me.start_count
  agent_id    = coder_agent.main.id
  instance_id = google_compute_instance.dev[0].instance_id
}

resource "coder_metadata" "workspace_info" {
  count       = data.coder_workspace.me.start_count
  resource_id = google_compute_instance.dev[0].id

  item {
    key   = "image"
    value = module.gce-container.container.image
  }
}

resource "coder_app" "jupyter" {
  count        = tobool(var.jupyterlab) ? 1 : 0
  agent_id     = coder_agent.main.id
  slug         = "jupyter"
  display_name = "JupyterLab"
  url          = "http://localhost:8888"
  icon         = "/icon/jupyter.svg"
  share        = "owner"
  subdomain    = true

  healthcheck {
    url       = "http://localhost:8888/api"
    interval  = 5
    threshold = 10
  }
}

module "vscode-web" {
  count          = tobool(var.codeserver) ? data.coder_workspace.me.start_count : 0
  source         = "registry.coder.com/coder/vscode-web/coder"
  version        = "1.3.0"
  agent_id       = coder_agent.main.id
  extensions     = ["ms-python.python", "ms-python.vscode-pylance"]
  install_prefix = "/tmp/.vscode-web"
  folder         = "/home/coder/${local.repo_name}"
  accept_license = true
}

resource "coder_app" "streamlit-app" {
  count        = tobool(var.streamlit) ? 1 : 0
  agent_id     = coder_agent.main.id
  slug         = "streamlit-app"
  display_name = "Search and Chat"
  url          = "http://localhost:8501"
  icon         = "https://icon.icepanel.io/Technology/svg/Streamlit.svg"
  subdomain    = false
  share        = "owner"

  healthcheck {
    url       = "http://localhost:8501/healthz"
    interval  = 5
    threshold = 6
  }
}
