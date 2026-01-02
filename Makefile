# MiniStatus-MVP Makefile
# Alternative installation method using standard 'make install'

.PHONY: install uninstall start stop restart status logs help

help:
	@echo "MiniStatus-MVP Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install    - Install and set up MiniStatus-MVP"
	@echo "  make uninstall  - Remove the service (keeps files)"
	@echo "  make start      - Start the service"
	@echo "  make stop       - Stop the service"
	@echo "  make restart    - Restart the service"
	@echo "  make status     - Check service status"
	@echo "  make logs       - View service logs"
	@echo "  make help       - Show this help message"

install:
	@echo "Installing MiniStatus-MVP..."
	@bash scripts/install.sh

uninstall:
	@echo "Uninstalling MiniStatus-MVP..."
	@bash scripts/uninstall.sh

start:
	@sudo systemctl start ministatus

stop:
	@sudo systemctl stop ministatus

restart:
	@sudo systemctl restart ministatus

status:
	@sudo systemctl status ministatus --no-pager -l

logs:
	@sudo journalctl -u ministatus -f

