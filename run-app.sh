#!/bin/bash
cd $HOME/digi
git pull origin main
gunicorn -b  0.0.0.0:5000 app:app
