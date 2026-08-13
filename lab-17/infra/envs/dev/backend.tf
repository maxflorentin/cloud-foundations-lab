terraform {
  backend "local" {
    path = "../../../.tfstate/dev/terraform.tfstate"
  }
}
