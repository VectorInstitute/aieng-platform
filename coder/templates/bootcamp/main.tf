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

data "coder_parameter" "gcp_project_id" {
  name      = "Google Compute Project ID"
  type      = "string"
  mutable   = false
  default   = ""
}

data "coder_parameter" "github_repo" {
  name      = "GitHub repository to clone"
  type      = "string"
  mutable   = false
  default   = ""
}

data "coder_parameter" "github_branch" {
  name      = "GitHub repository branch to checkout"
  type      = "string"
  mutable   = false
  default   = "main"
}

# https://registry.coder.com/modules/coder/gcp-region/coder
module "gcp_region" {
  source = "registry.coder.com/coder/gcp-region/coder"
  # This ensures that the latest non-breaking version of the module gets downloaded, you can also pin the module version to prevent breaking changes in production.
  version = "~> 1.0"
  regions = ["us", "europe"]
}

provider "google" {
  zone    = module.gcp_region.value
  project = data.coder_parameter.gcp_project_id.value
}

data "google_compute_default_service_account" "default" {}

data "coder_provisioner" "me" {}
data "coder_workspace" "me" {}
data "coder_workspace_owner" "me" {}

locals {
  # Ensure Coder username is a valid Linux username
  username = "coder"
  github_repo = data.coder_parameter.github_repo.value
  github_branch = data.coder_parameter.github_branch.value
  repo_name = replace(regex(".*/(.*)", data.coder_parameter.github_repo.value)[0], ".git", "")
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

    echo "Installing Code Server"

    # install and start code-server
    sudo curl -fsSL https://code-server.dev/install.sh | sh -s -- --method=standalone --prefix=/tmp/code-server
    /tmp/code-server/bin/code-server --auth none --port 13337 >/tmp/code-server.log 2>&1 &

    echo "Cloning git repository and checking out the dev branch"

    # Clone the GitHub repository
    cd "/home/${local.username}"

    if [ ! -d "${local.repo_name}" ] ; then
      git clone ${local.github_repo}
    fi

    cd ${local.repo_name}

    git checkout ${local.github_branch}

    echo "Running project init script"

    if [ ! -f ".coder/init.sh" ] ; then
      sh coder/init.sh
    fi

    echo "Startup script ran successfully!"

  EOT

  env = {
    GIT_AUTHOR_NAME     = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
    GIT_AUTHOR_EMAIL    = "${data.coder_workspace_owner.me.email}"
    GIT_COMMITTER_NAME  = coalesce(data.coder_workspace_owner.me.full_name, data.coder_workspace_owner.me.name)
    GIT_COMMITTER_EMAIL = "${data.coder_workspace_owner.me.email}"
  }
}

# See https://registry.terraform.io/modules/terraform-google-modules/container-vm
module "gce-container" {
  source  = "terraform-google-modules/container-vm/google"
  version = "3.0.0"

  container = {
    image   = "us-central1-docker.pkg.dev/axial-iris-462715-e6/vbootcamp/bootcamp-image:test"
    command = ["sh"]
    args    = ["-c", coder_agent.main.init_script]
    securityContext = {
      privileged : true
    }
    # Declare volumes to be mounted
    # This is similar to how Docker volumes are mounted
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
  ]
}

resource "google_compute_disk" "pd" {
  project = data.coder_parameter.gcp_project_id.value
  name  = "coder-${data.coder_workspace.me.id}-data-disk"
  type  = "pd-ssd"
  zone  = module.gcp_region.value
  size    = 10
}

resource "google_compute_instance" "dev" {
  zone         = module.gcp_region.value
  count        = data.coder_workspace.me.start_count
  name         = "coder-${lower(data.coder_workspace_owner.me.name)}-${lower(data.coder_workspace.me.name)}"
  machine_type = "e2-medium"
  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }
  boot_disk {
    initialize_params {
      image = module.gce-container.source_image
    }
  }
  attached_disk {
    source      = google_compute_disk.pd.self_link
    device_name = "data-disk-0"
    mode        = "READ_WRITE"
  }
  service_account {
    email  = data.google_compute_default_service_account.default.email
    scopes = ["cloud-platform"]
  }
  metadata = {
    "gce-container-declaration" = module.gce-container.metadata_value
  }
  labels = {
    container-vm = module.gce-container.vm_container_label
  }
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

resource "coder_app" "code-server" {
  agent_id     = coder_agent.main.id
  slug         = "code-server"
  display_name = "code-server"
  url          = "http://localhost:13337/?folder=/home/${local.username}/${local.repo_name}"
  icon         = "/icon/code.svg"
  subdomain    = false
  share        = "owner"

  healthcheck {
    url       = "http://localhost:13337/healthz"
    interval  = 5
    threshold = 6
  }
}

resource "coder_app" "streamlit-app" {
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
