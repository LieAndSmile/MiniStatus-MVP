provider "aws" {
  region = "us-east-1"
}

resource "aws_key_pair" "deployer" {
  key_name   = "ministatus-key"
  public_key = file("ministatus-key.pub")
}

resource "aws_instance" "ministatus" {
  ami           = "ami-08c40ec9ead489470"  # Ubuntu 22.04 LTS for us-east-1
  instance_type = "t2.micro"
  key_name      = aws_key_pair.deployer.key_name

  vpc_security_group_ids = [aws_security_group.allow_web.id]

  user_data = <<-EOF
              #!/bin/bash
              apt update
              apt install -y docker.io
              docker run -d -p 5000:5000 rilmay/ministatus
              EOF

  tags = {
    Name = "MiniStatus"
  }
}

resource "aws_security_group" "allow_web" {
  name        = "ministatus-sg"
  description = "Allow web traffic"

  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
