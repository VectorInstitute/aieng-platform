#!/usr/bin/env python3

import pandas as pd
import subprocess
import os


def log(message, log_file="/tmp/install.log", shell=True, env=None):
    """Run a shell command with optional logging."""
    if log_file:
        try:
            with open(log_file, 'a') as f:
                f.write(message)
        except IOError as e:
            print(f"Failed to write to log file {log_file}: {e}")


def create_users():
    """Create user accounts for Coder."""
    users = pd.read_csv('/tmp/users.csv')
    for index, row in users.iterrows():
        username = row['username']
        password = row['password']
        full_name = row['full_name']
        email = row['email']
        login_type = row['login_type']

        # Run a "coder users create" subprocess command with the above credentials
        try:
            subprocess.run(
                ["coder", "users", "create", "--username", username, "--password", password, "--full-name", full_name, "--email", email, "--login-type", login_type],
                check=True,
                shell=True,
                env=os.environ
            )
        except subprocess.CalledProcessError as e:
            log(f"Failed to create user {username}: {e}")
            continue


        log(f"User {username} created successfully with password: {password}.")


def configure():
    """Configure the Coder environment"""
    pass


def main():
    """Main function to run the setup."""
    try:
        #create_users()
        configure()
        print("Coder setup completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred during Coder setup: {e}")
        exit(1)


if __name__ == "__main__":
    main()

