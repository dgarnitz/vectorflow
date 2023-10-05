import subprocess
import os

def main():
    # Assuming setup.sh is in the same directory as this Python file.
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'setup.sh')
    subprocess.call([script_path])

if __name__ == "__main__":
    main()
