variable "project" {
    type = string
}

variable "region" {
    type = string
}

variable "zone" {
    type = string
}

variable "script_path" {
    type    = string
    default = "startup.sh"
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