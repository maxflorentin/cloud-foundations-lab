terraform {
  backend "local" {
    path = "../../../.tfstate/prod/terraform.tfstate"
  }
}
