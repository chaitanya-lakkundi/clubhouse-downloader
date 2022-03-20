#!/usr/bin/env sh

rsync -a --progress --exclude 'venv' --exclude '__pycache__' --exclude '.git*' --exclude '*.db'  . sambhasha:/var/www/html/chdl/
