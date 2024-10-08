import subprocess
import sys
import os

mixer_script_path = os.path.join(os.path.dirname(__file__), "mixer_script.py")
recommendation_script = os.path.join(os.path.dirname(__file__), "recommendation_script.py")
shuffle_script = os.path.join(os.path.dirname(__file__), "shuffle_script.py")

print("Running the mixer script")
try:
    subprocess.check_call([sys.executable, mixer_script_path])
    print("Mixer script completed successfully\n")
except subprocess.CalledProcessError as e:
    print(f"An error occurred while running the mixer script: {e}")
    sys.exit(1)

print("Running the recommendation script")
try:
    subprocess.check_call([sys.executable, recommendation_script])
    print("Recommendation script completed successfully\n")
except subprocess.CalledProcessError as e:
    print(f"An error occurred while running the recommendation script: {e}")
    sys.exit(1)

print("Running the shuffle script")
try:
    subprocess.check_call([sys.executable, shuffle_script])
    print("Shuffle script completed successfully\n")
except subprocess.CalledProcessError as e:
    print(f"An error occurred while running the shuffle script: {e}")
    sys.exit(1)

print("All scripts completed successfully")
