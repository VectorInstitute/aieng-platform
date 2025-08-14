variable "project" {
    type = string
}

variable "region" {
    type = string
}

variable "zone" {
    type = string
}

variable "user" {
    type = string
}

variable "script_path" {
    type    = string
    default = "startup.sh"
}

variable "public_key_path" {
    type = string
}

variable "machine_type" {
    type = string
}

variable "service_account_email" {
    type = string
}

variable "vm_name" {
    type = string
}