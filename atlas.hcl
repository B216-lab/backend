variable "database_url" {
  type    = string
  default = getenv("ATLAS_DATABASE_URL")
}

variable "dev_database_url" {
  type    = string
  default = getenv("ATLAS_DEV_DATABASE_URL")
}

env "local" {
  src = "file://db/schema.sql"
  dev = var.dev_database_url
  url = var.database_url
}
