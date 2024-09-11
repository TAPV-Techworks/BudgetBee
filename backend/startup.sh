#!/bin/sh

# Create the database file if it doesn't exist
if [ ! -f backend/flask_data.db ]; then
    touch backend/flask_data.db
    echo "Database file created successfully"
else
    echo "Database file already exists"
fi
