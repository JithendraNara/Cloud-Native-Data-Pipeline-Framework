# VPC Module - Multi-AZ Networking
variable "environment" { type = string }
variable "vpc_cidr" { type = string, default = "10.0.0.0/16" }
variable "azs" { type = list(string), default = ["us-east-1a", "us-east-1b"] }
variable "public_cidrs" { type = list(string), default = ["10.0.1.0/24", "10.0.2.0/24"] }
variable "private_cidrs" { type = list(string), default = ["10.0.10.0/24", "10.0.11.0/24"] }
variable "enable_nat" { type = bool, default = true }

output "vpc_id" { value = aws_vpc.main.id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "public_subnet_ids" { value = aws_subnet.public[*].id }
output "nat_gateway_ids" { value = aws_nat_gateway.main[*].id }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = { Name = "pipeline-vpc-${var.environment}", Environment = var.environment }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags = { Name = "pipeline-igw-${var.environment}" }
}

resource "aws_subnet" "public" {
  count = length(var.public_cidrs)
  vpc_id = aws_vpc.main.id
  cidr_block = var.public_cidrs[count.index]
  availability_zone = var.azs[count.index]
  map_public_ip_on_launch = true
  tags = { Name = "public-subnet-${count.index + 1}-${var.environment}" }
}

resource "aws_subnet" "private" {
  count = length(var.private_cidrs)
  vpc_id = aws_vpc.main.id
  cidr_block = var.private_cidrs[count.index]
  availability_zone = var.azs[count.index]
  tags = { Name = "private-subnet-${count.index + 1}-${var.environment}" }
}

resource "aws_eip" "nat" {
  count = var.enable_nat ? length(var.azs) : 0
  domain = "vpc"
  tags = { Name = "nat-eip-${count.index}-${var.environment}" }
}

resource "aws_nat_gateway" "main" {
  count = var.enable_nat ? length(var.azs) : 0
  allocation_id = aws_eip_nat[count.index].id
  subnet_id = aws_subnet.public[count.index].id
  tags = { Name = "nat-gw-${count.index}-${var.environment}" }
  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0" gateway_id = aws_internet_gateway.main.id }
  tags = { Name = "public-rt-${var.environment}" }
}

resource "aws_route_table" "private" {
  count = length(var.azs)
  vpc_id = aws_vpc.main.id
  route { cidr_block = "0.0.0.0/0" nat_gateway_id = aws_nat_gateway.main[count.index].id }
  tags = { Name = "private-rt-${count.index}-${var.environment}" }
}

resource "aws_route_table_association" "public" {
  count = length(var.public_cidrs)
  subnet_id = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = length(var.private_cidrs)
  subnet_id = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}
