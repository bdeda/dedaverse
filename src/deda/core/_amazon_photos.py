# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
import os
import sys
import time
import platform
from pathlib import Path

# Conditional debugger import (only on Windows and when WING_DEBUG env var is set)
if platform.system() == 'Windows' and os.getenv('WING_DEBUG'):
    try:
        wing_path = Path(r'C:\Program Files\Wing Pro 10')
        if wing_path.exists():
            sys.path.insert(0, str(wing_path))
            import wingdbstub
    except ImportError:
        pass
    finally:
        if sys.path and sys.path[0] == str(wing_path):
            sys.path = sys.path[1:]
    
from marionette_driver.errors import MarionetteException
from marionette_driver.expected import element_displayed, element_not_displayed
from marionette_driver.keys import Keys
from marionette_driver.marionette import Marionette
from marionette_driver.by import By
from marionette_driver.wait import Wait


client = Marionette(host='localhost', port=2828)
client.start_session()

if not client.get_url().startswith("https://www.amazon.com/photos/"):
    print("Unexpected URL: %s" % client.get_url())
    print("Make sure you're logged in to Amazon Photos.")
    client.delete_session()
    exit(1)


hrefs = set()
existing_window_handles = set(client.chrome_window_handles)


def wait_and_find(finder, by, value):
    Wait(finder).until(element_displayed(by, value))
    return finder.find_element(by, value)


def download(link):
    href = link.get_attribute("href")
    if href in hrefs:
        return False

    print("Found " + href)
    hrefs.add(href)
    found_new = True
    link.click()

    image_head = wait_and_find(client, By.CLASS_NAME, "image-head")
    wait_and_find(image_head, By.CLASS_NAME, "toggle").click()
    wait_and_find(image_head, By.CLASS_NAME, "download").click()

    with client.using_context(client.CONTEXT_CHROME):
        # Once the total number of windows has exceeded the original number of windows,
        # we know the dialog has finished opening.
        while len(client.chrome_window_handles) == len(existing_window_handles):
            time.sleep(1)

        new_handle = (set(client.chrome_window_handles) - existing_window_handles).pop()
        content_window = client.current_chrome_window_handle
        client.switch_to_window(new_handle, focus=True)

        wait_and_find(client, By.ID, "save").click()

        # The dialog buttons are XUL elements, not HTML elements, and so
        # Marionette seems unable to see them. Fortunately, we can simulate
        # the OK click using Javascript and then just close the dialog.
        client.execute_script("dialog.onOK();")
        client.close_chrome_window();

        client.switch_to_window(content_window)

    wait_and_find(image_head, By.CLASS_NAME, "back").click()
    Wait(client).until(element_not_displayed(By.CLASS_NAME, "image-head"))

    return True


while True:
    try:
        num_downloaded = 0

        for link in client.find_elements(By.CLASS_NAME, "node-link"):
            if download(link):
                num_downloaded += 1

        if num_downloaded == 0:
            print("No new photos found.")
            break

        print("Scrolling down")
        client.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
        print("Waiting...")
        time.sleep(3)
    except MarionetteException as err:
        print("Error: %s (will keep trying)" % err)


print("Closing session.")
client.delete_session()