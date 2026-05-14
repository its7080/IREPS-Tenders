"""
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||     
Author: Anupam Manna
Email ID: am7059141480@gmail.com
Mobile No: +91 7059141480
Date: October 2, 2023
Description: IREPS tenders automation.
||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||       
"""

import json
import os
import pandas as pd
import subprocess
import sys
import re
# from openpyxl import load_workbook
import time
# import tempfile
# import shutil
# import logging
import datetime
import concurrent.futures
import threading
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
# from email.mime.application import MIMEApplication
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
# import shutil
# import urllib.request
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup
# from urllib.parse import urlparse
import requests
import xlsxwriter
import math
import pdfplumber
import platform
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# from chrome_updater import ChromeUpdater
from Program_Files.scraping_library import check_internet_connection
# from Program_Files.scraping_library import get_folder_size_in_mb
# from Program_Files.scraping_library import delete_empty_folders
from Program_Files.scraping_library import delete_folder
from Program_Files.scraping_library import packaging
from Program_Files.scraping_library import create_folder_if_not_exists
from Program_Files.scraping_library import is_android_device_connected
# from Program_Files.scraping_library import send_email
from Program_Files.scraping_library import countdown_timer
from Program_Files.scraping_library import delete_xlsx_files
from Program_Files.scraping_library import no_adb_mail
from Program_Files.scraping_library import skip_zones
from Program_Files.scraping_library import get_current_device_serial
from Program_Files.captcha_solver import predict_captcha

import base64
import io
from PIL import Image
# # =======================
# # chrome_updater
# # =======================
# # Create an instance of ChromeUpdater
# updater = ChromeUpdater()

# # Step 1: Open Chrome with Selenium
# driver = updater.relaunch_chrome_with_playwright()

# # Step 2: Close Chrome to prepare for the update
# time.sleep(5)  # Simulate some activity
# updater.close_chrome(driver)

# # Step 3: Download and install the latest version of Chrome
# updater.download_chrome_installer()
# updater.install_chrome()

# # Step 4: Relaunch Chrome after the update
# driver = updater.relaunch_chrome_with_playwright()




#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>># Global Variables
# Determine script directory
script_path = os.path.abspath(sys.argv[0])  # Absolute path of the executable
script_dir_path = os.path.dirname(script_path)

# Define directories and file paths relative to the script directory
# input_files_dir = os.path.join(script_dir_path, "Input_Files")
output_files_dir = os.path.join(script_dir_path, "Output_Files")
program_files_dir = os.path.join(script_dir_path, "Program_Files")


# Join the script path with the source path
temp_dir_path = os.path.join(program_files_dir, "ireps_temp")
# print(temp_dir_path)

# email_file_path = os.path.join(input_files_dir, "emailid_list.txt")
# print(email_file_path)
# sheet_names_file_path = os.path.join(input_files_dir,"sheet_names.txt")
# print(sheet_names_file_path)
script_log_file_path = os.path.join(program_files_dir, "script_log.log" )
# print(script_log_file_path)
config_file_path = os.path.join(program_files_dir, "Configration.json")
# print(config_file_path)
org_file_path = os.path.join(program_files_dir, "Organization_list.txt")
# print(org_file_path)
ireps_data = os.path.join(program_files_dir, "ireps_data.pkl")
# print(ireps_data)
# file_to_save_path = os.path.join(input_files_dir, "send_mail_log.txt")
# print(file_to_save_path)

tender_pdf_file_path = os.path.join(temp_dir_path, "tender.pdf")
# print(tender_pdf_file_path)

_thread_local = threading.local()
_otp_lock = threading.Lock()


class TimeoutException(Exception):
    """Compatibility exception used by the former Selenium flow."""


class NoSuchElementException(Exception):
    """Raised when a Playwright locator cannot resolve an element."""


class NoAlertPresentException(Exception):
    """Raised when code asks for an alert but no dialog was captured."""


class By:
    ID = "id"
    XPATH = "xpath"
    CSS_SELECTOR = "css selector"


def _selector(by, value):
    if by == By.ID:
        return f"#{value}"
    if by == By.XPATH or by == "xpath":
        return f"xpath={value}"
    if by == By.CSS_SELECTOR:
        return value
    return value


def _active_pdf_path():
    return getattr(_thread_local, "tender_pdf_file_path", tender_pdf_file_path)


def _safe_filename(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "org"


class PlaywrightElement:
    def __init__(self, driver, locator):
        self.driver = driver
        self.locator = locator

    def click(self):
        before_pages = list(self.driver.context.pages)
        try:
            # no_wait_after avoids false timeouts on IREPS actions that submit forms
            # or open tabs but keep the original page in a busy state.
            self.locator.click(timeout=self.driver.default_timeout, no_wait_after=True)
        except PlaywrightTimeoutError:
            # The element can be visible and enabled but Playwright may still time out
            # waiting for the browser action to finish. Fall back to the DOM click so
            # one slow organization does not abort the whole scraping run.
            self.locator.evaluate("element => element.click()", timeout=self.driver.default_timeout)

        self.driver._sync_pages()
        for page in self.driver.context.pages:
            if page not in before_pages:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except PlaywrightTimeoutError:
                    pass
                self.driver._register_page(page)
        return None

    def get_attribute(self, name):
        if name == "innerText":
            return self.locator.inner_text(timeout=self.driver.default_timeout)
        return self.locator.get_attribute(name, timeout=self.driver.default_timeout)


class Select:
    def __init__(self, element):
        self.element = element

    def select_by_value(self, value):
        self.element.locator.select_option(value=str(value), timeout=self.element.driver.default_timeout)

    @property
    def options(self):
        return [
            PlaywrightElement(self.element.driver, self.element.locator.locator("option").nth(index))
            for index in range(self.element.locator.locator("option").count())
        ]


class PlaywrightAlert:
    def __init__(self, driver):
        self.driver = driver
        if driver.last_dialog is None:
            raise NoAlertPresentException("No alert present")
        self._dialog = driver.last_dialog
        self.text = self._dialog.message

    def accept(self):
        try:
            self._dialog.accept()
        finally:
            self.driver.last_dialog = None


class Alert:
    def __init__(self, driver):
        self._alert = PlaywrightAlert(driver)

    @property
    def text(self):
        return self._alert.text

    def accept(self):
        self._alert.accept()


class _SwitchTo:
    def __init__(self, driver):
        self.driver = driver

    def window(self, handle):
        self.driver.switch_to_window(handle)

    @property
    def alert(self):
        return PlaywrightAlert(self.driver)


class PlaywrightDriver:
    def __init__(self, page, context, browser_handle, playwright_handle, default_timeout=10000):
        self.page = page
        self.context = context
        self.browser_handle = browser_handle
        self.playwright_handle = playwright_handle
        self.default_timeout = default_timeout
        self.last_dialog = None
        self.switch_to = _SwitchTo(self)
        self._known_pages = []
        self._register_page(page)

    def _register_page(self, page):
        if page not in self._known_pages:
            self._known_pages.append(page)
            page.on("dialog", self._capture_dialog)

    def _capture_dialog(self, dialog):
        self.last_dialog = dialog

    def _sync_pages(self):
        for page in self.context.pages:
            self._register_page(page)

    @property
    def page_source(self):
        return self.page.content()

    @property
    def current_url(self):
        return self.page.url

    @property
    def current_window_handle(self):
        return self.page

    @property
    def window_handles(self):
        self._sync_pages()
        return list(self.context.pages)

    def switch_to_window(self, handle):
        self._sync_pages()
        self.page = handle
        try:
            self.page.bring_to_front()
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

    def set_page_load_timeout(self, seconds):
        self.default_timeout = int(seconds * 1000)
        self.page.set_default_navigation_timeout(self.default_timeout)

    def implicitly_wait(self, seconds):
        self.default_timeout = int(seconds * 1000)
        self.context.set_default_timeout(self.default_timeout)

    def get(self, url):
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=self.default_timeout)
        except PlaywrightTimeoutError as exc:
            raise TimeoutException(str(exc)) from exc

    def refresh(self):
        try:
            self.page.reload(wait_until="domcontentloaded", timeout=self.default_timeout)
        except PlaywrightTimeoutError as exc:
            raise TimeoutException(str(exc)) from exc

    def find_element(self, by=None, value=None):
        if value is None:
            value = by
            by = None
        locator = self.page.locator(_selector(by, value)).first
        try:
            locator.wait_for(state="attached", timeout=self.default_timeout)
            return PlaywrightElement(self, locator)
        except PlaywrightTimeoutError as exc:
            raise NoSuchElementException(str(exc)) from exc

    def find_elements(self, by=None, value=None):
        if value is None:
            value = by
            by = None
        locator = self.page.locator(_selector(by, value))
        return [PlaywrightElement(self, locator.nth(index)) for index in range(locator.count())]

    def execute_script(self, script):
        return self.page.evaluate(script)

    def close_current_page(self):
        try:
            self.page.close()
        except Exception:
            pass
        self._sync_pages()

    def close(self):
        try:
            self.page.close()
        except Exception:
            pass
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self.browser_handle.close()
        except Exception:
            pass
        self.playwright_handle.stop()


class WebDriverWait:
    def __init__(self, driver, timeout):
        self.driver = driver
        self.timeout = timeout

    def until(self, condition):
        end_time = time.time() + self.timeout
        last_error = None
        while time.time() < end_time:
            try:
                value = condition(self.driver)
                if value:
                    return value
            except Exception as exc:
                last_error = exc
            time.sleep(0.25)
        raise TimeoutException(str(last_error) if last_error else "Timed out waiting for condition")


class EC:
    @staticmethod
    def element_to_be_clickable(locator_tuple):
        by, value = locator_tuple

        def _predicate(driver):
            element = driver.find_element(by, value)
            if element.locator.is_visible() and element.locator.is_enabled():
                return element
            return False

        return _predicate


#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>># Global Variables

# List to store the organization
organizations = []

# Read data from the text file
with open(org_file_path, 'r') as file:
    lines = file.readlines()

for line in lines:
    # Check if the line starts with '#' and ignore those lines
    if not line.startswith('#'):
        parts = line.strip().split(': ')
        if len(parts) == 2:
            number = parts[0]
            name = parts[1]
            organizations.append((number, name))




# Load the JSON data from the file
with open(config_file_path, 'r') as file:
    data = json.load(file)
# Extract values from the JSON data
browser = data['browser']
adb_value = data['adb_device']
captcha_manual_input = data["captcha_manual_input"]
adb_device_ip = data['adb_device_ip']
mobile_no = data.get('mobile_no')
dump_location = data.get('dump_location')
excel_file_path = data.get('excel_file_path')
# otp_file_location = data['otp_file_location']
notification_emailids = data['notification_emailids']
receiver_emailids = data['receiver_emailids']
# print(notification_emailids)
# time.sleep(1000)


# Edit the value of "signal_ireps"
data["signal_ireps"] = "FALSE"
data["signal_datelog"] = "FALSE"
# Write the modified data back to the file
with open(config_file_path, 'w') as file:
    json.dump(data, file, indent=4) 

#----------------------------------------------------------------------------------------------- Extension to global variable






# Load dump location from JSON file
def load_otp():
    try:
        with open(config_file_path, "r") as file:
            data = json.load(file)
            return data.get("otp")
    except FileNotFoundError:
        return None
    




# Load dump location from JSON file
def load_otp_date():
    try:
        with open(config_file_path, "r") as file:
            data = json.load(file)
            return data.get("otp_date")
    except FileNotFoundError:
        return None
    





def is_otp_valid():
    # Get the current date
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    otp_date = load_otp_date()
    otp = load_otp()
    # Check if the dates match
    if current_date == otp_date: # date
        print(f"The OTP for today is: {otp}")
        return True
    else:
        print("No atching OTP found for today's date.")
        return False
    



def is_under_maintenance(driver, url):
    # Check if the page contains the specified text
    if "Module under maintenance" in driver.page_source:
        print(f"{url}  -  Module under maintenance")
    else:
        print(f"{url} link is Accessible ")
    return driver




# def get_verification(driver):
#     if captcha_manual_input == 1:

#          # blue #3BB9FF & red #640A0A
#     # Find all img elements inside the span with id "verimage" using XPath
#     img_tags = driver.find_elements(By.XPATH, "//span[@id='verimage']//img")

#     # Iterate through the img elements
#     for img_tag in img_tags:
#         src = img_tag.get_attribute("src")
#         if "Captcha.jpg?r=" in src:
#             captcha_chars = src.split('Captcha.jpg?r=')[1][:6]
#             # print("Image Source:", src)
#             print("verification Code: ", captcha_chars)
#     return driver, captcha_chars


def get_verification(driver):
    captcha_chars = None

    if captcha_manual_input == 1:
        # Locate the captcha <img>
        img_element = driver.find_element(By.ID, "imgCaptcha")
        src = img_element.get_attribute("src")

        if src.startswith("data:image"):
            # Base64 decode
            img_data = src.split(",")[1]
            image = Image.open(io.BytesIO(base64.b64decode(img_data)))
            image.show()  # Opens the image in default viewer

        # Ask user input
        captcha_chars = input("Enter CAPTCHA from the image: ").strip()

    else:
        # Step 1: Get captcha image element
        img_element = driver.find_element(By.ID, "imgCaptcha")
        src = img_element.get_attribute("src")

        # Save captcha image to temp.png
        if src.startswith("data:image"):  # If base64 encoded
            header, encoded = src.split(",", 1)
            data = base64.b64decode(encoded)
            with open("temp.png", "wb") as f:
                f.write(data)
        else:  # If src is a URL
            response = requests.get(src)
            with open("temp.png", "wb") as f:
                f.write(response.content)

        # Step 2: Run prediction
        test_image = "temp.png"
        predicted_text = predict_captcha(os.path.join(program_files_dir, "captcha_model.pth"), test_image)
        print(f"Predicted text: {predicted_text}")

        # Step 3: Remove temp.png
        if os.path.exists("temp.png"):
            os.remove("temp.png")

        captcha_chars = predicted_text.strip()


    return driver, captcha_chars





def login(driver, mobile_no):
    """
    Log in to a website using the provided WebDriver instance and mobile number.
    
    Args:
        driver (WebDriver): Selenium WebDriver instance for browser.
        mobile_no (str): Mobile number for login.
    
    Returns:
        WebDriver: Updated WebDriver instance after login, or None if login fails.
    """

    # Attempt to refresh the page up to 3 times if a timeout occurs
    for _ in range(3):
        try:
            driver.refresh()
            break
        except TimeoutException:
            print("Timeout occurred. Retrying refresh...")
            time.sleep(2)
    else:
        raise TimeoutException("Exceeded maximum retries. Unable to refresh.")

    time.sleep(3)  # Short delay before starting login

    # Attempt the login process up to 3 times
    for attempt in range(100):
        try:
            # Accept alert if present, then proceed
            Alert(driver).accept()
        except:
            pass  # Ignore if no alert

        # Get verification code and OTP, and fill in login details
        driver, ver_code = get_verification(driver)
        if ver_code is None:
            return None  # Return None if verification retrieval fails

        otp = load_otp()
        driver.execute_script(f"document.getElementById('mobileNo').value='{mobile_no}'")
        driver.execute_script(f"document.getElementById('verification').value='{ver_code}'")
        driver.execute_script(f"document.getElementById('otp').value='{otp}'")

        # Click the "Proceed" button and wait for the "custumSearchId" element
        time.sleep(2)
        driver.find_element("xpath", "//input[@value='Proceed']").click()

        try:
            driver.find_element(By.ID, "custumSearchId").click()
            return driver  # Return driver if login succeeds
        except Exception as e:
            print(f"Attempt {attempt + 1} failed - Exception: {e}")
            driver.get("https://www.ireps.gov.in/epsn/anonymSearch.do")
            time.sleep(5)

    return driver  # Return driver if all login attempts fail


# def login(driver, mobile_no):

#     retries = 0
#     while retries < 3:
#         try:
#             driver.refresh()
#             # If the refresh succeeds, break out of the loop
#             break
#         except TimeoutException:
#             print("Timeout exception occurred. Retrying...")
#             retries += 1
#             # Add some delay before retrying to avoid overwhelming the server
#             time.sleep(2)
#     else:
#         # If all retries fail, raise the TimeoutException
#         raise TimeoutException("Exceeded maximum retries. Unable to refresh.")

#     time.sleep(3)

#     # Retry login process up to 3 times
#     for attempt in range(3):
#         try:

#             try:
#                 alert = Alert(driver)
#                 alert.accept()
#             except:
#                 pass

#             driver, ver_code = get_verification(driver)

#             if ver_code is None:
#                 return None

#             otp = load_otp()
#             # Fill in login details and proceed
#             driver.execute_script("document.getElementById('mobileNo').value='" + mobile_no + "'")
#             time.sleep(1)
#             driver.execute_script("document.getElementById('verification').value='" + ver_code + "'")
#             time.sleep(1)
#             driver.execute_script("document.getElementById('otp').value='" + otp + "'")
#             time.sleep(2)
#             driver.find_element("xpath", "//input[@value='Proceed']").click()

#             # WebDriverWait block to wait for the presence of the element with ID "customSearchId"
#             driver.find_element(By.ID, "custumSearchId").click()
#             # If everything is successful, break out of the loop
#             return driver

#         except Exception as e:
#             # Handle other exceptions while clicking 'Custom Search' button
#             print(f"Attempt {attempt + 1} login or Custom Search button  -  Exception") # {e}")
#             driver.get("https://www.ireps.gov.in/epsn/anonymSearch.do")
#             time.sleep(5)

#     return driver



def is_no_result_found_present_in_page(driver):
    """
    Check if the page contains the "No Results Found" message.
    
    Args:
        driver (WebDriver): The Selenium WebDriver instance for interacting with the page.

    Returns:
        tuple: (bool, driver) where the boolean is True if "No Results Found" is present, False otherwise.
    """
    try:
        # Get the page source using Selenium
        page_source = driver.page_source

        # Parse the HTML content with BeautifulSoup
        soup = BeautifulSoup(page_source, 'html.parser')

        # Find the element containing the specific class and style attributes
        result_element = soup.find('td', {'class': 'formLabel', 'style': 'color: #C00000'})

        # Check if the element contains the text "No Results Found"
        if result_element and "No Results Found" in result_element.get_text(strip=True):
            print("No Results Found in the page.\n")
            return True, driver

        return False, driver
    
    except NoSuchElementException as e:
        print(f"An error occurred while checking the page: {e}")
        return False, driver








def _wait_for_new_window(driver, previous_handles, timeout=10):
    """Return a newly opened Playwright page, or None if no tab appears."""
    deadline = time.time() + timeout
    previous_handles = set(previous_handles)

    while time.time() < deadline:
        handles = driver.window_handles
        new_handles = [handle for handle in handles if handle not in previous_handles]
        if new_handles:
            new_handle = new_handles[-1]
            driver.switch_to.window(new_handle)
            return new_handle
        time.sleep(0.25)

    return None


def _close_child_windows(driver, initial_handle):
    """Close every open page except the search-results page."""
    for window_handle in list(driver.window_handles):
        if window_handle == initial_handle:
            continue
        try:
            driver.switch_to.window(window_handle)
            time.sleep(0.25)
            driver.close_current_page()
        except Exception:
            pass
    driver.switch_to.window(initial_handle)


def download_pdf(url, retries=5):
    for i in range(retries):
        try:
            response = requests.get(url, timeout=10)
            with open(_active_pdf_path(), 'wb') as output_file:
                output_file.write(response.content)
            print("Download successful")
            return True
        except Exception as e:
            print(f"Attempt ({i+1}/{retries}) failed. Retrying... to Download")
            time.sleep(0.5)  # wait for 1 second before retrying
    else:
        print("All Download attempts failed.")
        return False




def getpdfdata():

    # Extract PDF heading
    with pdfplumber.open(_active_pdf_path()) as pdf_heading:
        first_page = pdf_heading.pages[0]
        pdf_heading_text = first_page.extract_text()
        # Extract the first line assuming it contains the main heading
        dept_rly = pdf_heading_text.split('\n')[0].strip()


    # Extract table data
    with pdfplumber.open(_active_pdf_path()) as pdf:
        table = pdf.pages[0].extract_tables()[0]
        # Extracting table data
        table = [[value for value in sublist if value is not None] for sublist in table]
        new_table = [row[i*2:i*2+2] for row in table for i in range(len(row) // 2)] + [row for row in table if len(row) <= 2]
        # print(new_table, type(new_table))
        # time.sleep(3000)
        # Replace '\n' with space in the entire table
        # Replace '\n' with space in the entire table
        new_table = [[cell.replace('\n', ' ') for cell in row] for row in new_table]
        # print(nwe_table)
        # time.sleep(3000)

        extracted_info = {}
        keys_to_extract = ['Name of Work', 'Bidding type', 'Tender Type', 'Bidding System', 'Tender Closing Date Time', 'Date Time Of Uploading Tender', 'Pre-Bid Conference Date Time', 'Advertised Value', 'Earnest Money (Rs.)', 'Contract Type']

        for item in new_table:
            if item[0] in keys_to_extract and len(item) > 1:
                extracted_info[item[0]] = item[1]

        # Extracting text data
        with pdfplumber.open(_active_pdf_path()) as pdf_text:
            page_text = pdf_text.pages[0].extract_text()
            tender_no_index = page_text.find("Tender No:")
            if tender_no_index != -1:
                tender_no_text = page_text[tender_no_index + len("Tender No:"):].strip()
                tender_no = tender_no_text.split('\n')[0].strip() if '\n' in tender_no_text else tender_no_text
                tender_no = tender_no[:-36]
        # Extracted information
        name_of_work = extracted_info.get('Name of Work', '')
        bidding_type = extracted_info.get('Bidding type', '')
        tender_type = extracted_info.get('Tender Type', '')
        bidding_system = extracted_info.get('Bidding System', '')
        tender_closing_date_time = extracted_info.get('Tender Closing Date Time', '')
        date_time_of_uploading_tender = extracted_info.get('Date Time Of Uploading Tender', '')
        pre_bid_conference_date_time = extracted_info.get('Pre-Bid Conference Date Time', '')
        advertised_value = extracted_info.get('Advertised Value', '')
        earnest_money = extracted_info.get('Earnest Money (Rs.)', '')
        contract_type = extracted_info.get('Contract Type', '')

        print("Department:", dept_rly)
        print("Tender No:", tender_no)
        print("Name of Work:", name_of_work)
        print("Bidding Type:", bidding_type)
        print("Tender Type:", tender_type)
        print("Bidding System:", bidding_system)
        print("Tender Closing Date and Time:", tender_closing_date_time)
        print("Date and Time of Uploading Tender:", date_time_of_uploading_tender)
        print("Pre-Bid Conference Date and Time:", pre_bid_conference_date_time)
        print("Advertised Value:", advertised_value)
        print("Earnest Money:", earnest_money)
        print("Contract Type:", contract_type)
        # print(new_table)
        # time.sleep(3000)

        return dept_rly, tender_no, name_of_work, bidding_type, tender_type, bidding_system, tender_closing_date_time, date_time_of_uploading_tender, pre_bid_conference_date_time, advertised_value, earnest_money, contract_type





def tenders(driver, org_number, org_name, program_file_dir):
    for _ in range(3):  # Try the action three times
        try:
            # Locate the dropdown element using an appropriate selector
            dropdown_element = driver.find_element(By.ID, "organization")
            # Create a Select object and interact with the dropdown
            select = Select(dropdown_element)

            # Select option by value
            select.select_by_value(org_number)

            time.sleep(1)

            # Double select organization
            # Check if the element is still present
            if dropdown_element:
                driver.execute_script("document.getElementById('organization').value='"+ org_number +"'")
            else:
                print("Element with ID 'organization' not found")
            
            # If everything is successful, break out of the loop
            break

        except Exception as e:
            # Handle other exceptions while clicking organization dropdown button
            print(f"organization dropdown  -  Exception")
            driver.refresh()
            time.sleep(2)


    """Stores all options in a dictionary. then print the zone list"""

    time.sleep(1)
    railway_zone_dropdown = Select(driver.find_element(By.XPATH, "//*[@id='railwayZone']"))
    # print(railway_zone_dropdown)
    options = railway_zone_dropdown.options
    # print(options)

    options_dict = {}
    for option in options:
        value = option.get_attribute("value")
        text = option.get_attribute("innerText")
        options_dict[value] = text

    # Print the options dictionary
    print("\n--------- ZONE LIST ---------")
    for zone in options_dict.values():
        if zone in skip_zones:
            continue  # Skip the current iteration and move to the next one
        print(zone)

    """ End """


    for zone_number, zone in options_dict.items():
        last_tender = False
        if zone in skip_zones: # this condition skip all zones inside skip_zones
            continue  # Skip the current iteration and move to the next one
        print(f"\nScraping ZONE -> {zone}")
        print("----------------")


        for _ in range(3):  # Try the action three times
            try:
                # filling search criteria
                time.sleep(3)
                driver.execute_script("document.getElementById('organization').value='"+ org_number +"'")
                time.sleep(3)
                driver.execute_script("document.getElementById('workArea').value='WT'") # works
                time.sleep(3)
                driver.execute_script("document.getElementById('railwayZone').value='"+ zone_number +"'")
                time.sleep(3)
                driver.execute_script("document.getElementById('tenderType').value=2") # open
                time.sleep(3)
                driver.execute_script("document.getElementById('tenderStage').value=1") # published
                time.sleep(3)
                driver.execute_script("document.getElementsByName('selectDate')[0].value = 'TENDER_OPENING_DATE'") # Tender Closing Date
                # Get the current date
                current_date = datetime.datetime.now()
                # Add four months to the current date
                four_months_later = current_date + relativedelta(months=4)
                # Format the date as a string (optional)
                formatted_date = four_months_later.strftime("%d/%m/%Y")
                driver.execute_script("document.getElementById('ddmmyyDateformat2').value='" + formatted_date + "'")
                time.sleep(0.5)
                # driver.find_element(By.XPATH, "//input[@value='Show Results']").click()
                xpath = "//input[@value='Show Results']"
                element = driver.find_element(By.XPATH, xpath)
                element.click()

                # If everything is successful, break out of the loop
                break

            except Exception as e:
                # Handle other exceptions while clicking 'Custom Search' button
                print(f"Show Results button  -  Exception")
                driver.refresh()
                time.sleep(2)

        result, driver = is_no_result_found_present_in_page(driver)

        packages = packaging()
        if result:
            continue

        try:
            tender_count = 0
            time.sleep(3.5)
            
            # Get the page source and parse it with BeautifulSoup
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            # Find all 'b' tags within 'tr' tags
            b_tags = soup.find_all('b')
            
            # Iterate over the 'b' tags
            for i in range(len(b_tags)):
                # If the 'b' tag contains "Tender search results"
                if "Tender search results" in b_tags[i].text:
                    # If there is a next 'b' tag, print it
                    if i + 1 < len(b_tags):
                        tender_count = b_tags[i + 1].text
                        if int(tender_count) < 1 :  # Check if tender_count exists but is None
                            print("Unable to get tender search result, Variable is None and has no value assigned. ", tender_count)
                            continue
                        print("Tender search results ", tender_count)
                    break

        except Exception as e:
            print(f"An error occurred: Tender search results", e)
            break

        # # Get the page source and parse it with BeautifulSoup
        # soup = BeautifulSoup(driver.page_source, 'html.parser')
        # # Find all 'b' tags within 'tr' tags
        # b_tags = soup.find_all('b')
        # # Iterate over the 'b' tags
        # for i in range(len(b_tags)):
        #     # If the 'b' tag contains "Tender search results"
        #     if "Tender search results" in b_tags[i].text:
        #         # If there is a next 'b' tag, print it
        #         if i+1 < len(b_tags):
        #             tender_count = b_tags[i+1].text
        #             print("Tender search results ", tender_count)
        #         break


        # Get the current date and time
        current_date = datetime.datetime.now()
        # Format the date and time string
        fname = current_date.strftime("%d-%m-%Y %H_%M_%S")
        # Create a file name using the value and the formatted date and time
        file_name = f'{zone}_{fname}.xlsx'
        # Create a file path for the new Excel workbook
        org_output_dir = os.path.join(program_files_dir, org_name)
        os.makedirs(org_output_dir, exist_ok=True)
        file_path = os.path.join(org_output_dir, file_name)
        # Create a new Excel workbook and a worksheet within it
        workbook = xlsxwriter.Workbook(file_path)
        worksheet1 = workbook.add_worksheet("ListOfTenders")
        # Write the column headers in the worksheet
        headers = ["Zone", "Dept.", "Tender No.", "Tender Title", "Type", "Due Date/Time", "Due Days", "Advertised Value", "Doc Link", "Bidding type", "Bidding System", "Date Time Of Uploading Tender", "Pre-Bid Conference Date Time", "Earnest Money (Rs.)", "Contract Type"]
        for index, header in enumerate(headers):
            worksheet1.write(0, index, header)


        # Calculate the number of pages based on the tender count
        tender_count = int(tender_count)
        decimal_number = tender_count / 25
        # Round up to the nearest integer to get the page count
        page_count = math.ceil(decimal_number)
        # Print the number of pages
        print("Pages = ", page_count)


        cnt = 1
        k = 0
        # Loop through all the pages
        while cnt <= page_count:
            time.sleep(3)
            for _ in range(3):  # Try the action three times
                try:
                    # If the element is found, you can perform further actions here
                    a_tags = driver.find_elements(By.CSS_SELECTOR, "a[onclick]")      
                    # If everything is successful, break out of the loop
                    break
                except Exception as e:
                    # Handle other exceptions while clicking 'Custom Search' button
                    print(f"a_tags tender link - Exception")
                    time.sleep(2)
                    continue

            if not a_tags:
                break

            filtered_a_tags = [tag for tag in a_tags if 'postRequestNewWindow(\'/epsn/nitViewAnonyms/rfq/nitPublish.do?' in tag.get_attribute('onclick')]

            # Get the initial window handle
            initial_handle = driver.current_window_handle
            for a_tag in filtered_a_tags:
                k += 1
                print('\r' + "Tender  : " + str(k) + " ", end='')

                handles_before_tender = driver.window_handles
                try:
                    a_tag.click()
                    # WebDriverWait(driver, 20).until(lambda x: x.execute_script('return document.readyState') == 'complete')
                except Exception as e:
                    print("Result page a_tags tender link click - Exception")
                    driver.switch_to.window(initial_handle)
                    time.sleep(2)
                    continue

                tender_window = _wait_for_new_window(driver, handles_before_tender, timeout=10)
                if tender_window is None:
                    print("Tender detail window did not open - skipping tender")
                    driver.switch_to.window(initial_handle)
                    time.sleep(2)
                    continue

                # # checkpoint
                # temp_url = driver.current_url
                # print(" >> ", temp_url)


                handles_before_pdf = driver.window_handles
                try:
                    time.sleep(1)
                    xpath = "//a[contains(text(), 'Download Tender Doc. (Pdf)')]"
                    download_button = driver.find_element(By.XPATH, xpath)
                    download_button.click()
                except Exception as e:
                    # Handle other exceptions while clicking 'Custom Search' button
                    print(f"Download Tender Doc. (Pdf) button - Exception")
                    _close_child_windows(driver, initial_handle)
                    time.sleep(2)
                    continue

                pdf_window = _wait_for_new_window(driver, handles_before_pdf, timeout=10)
                if pdf_window is None:
                    print("Tender PDF window did not open - skipping tender")
                    _close_child_windows(driver, initial_handle)
                    time.sleep(2)
                    continue


                # # Define a function to wait for the page to fully load
                # def page_fully_loaded(driver):
                #     return driver.execute_script("return document.readyState") == "complete"

                # # Wait for the page to fully load
                # WebDriverWait(driver, 10).until(page_fully_loaded)

                pdf_url = driver.current_url
                print(" ", pdf_url)

                # # Execute JavaScript to get the current window's URL
                # window_url = driver.execute_script("return window.location.href;")
                # url_pattern = re.compile(r'^https:\/\/www\.ireps\.gov\.in\/ireps\/works\/pdfdocs\/.*\.pdf$')

                # while True:
                #     if url_pattern.match(pdf_url):
                #         print("URL is valid. ", pdf_url)
                #         break
                #     else:
                #         print("URL is not valid.")
                #         time.sleep(0.25)
                #         pdf_url = driver.current_url
                #         continue

                if pdf_url.endswith(".pdf"):
                    download_pdf(pdf_url)
                else:
                    _close_child_windows(driver, initial_handle)
                    continue

                dept_rly, tender_no, name_of_work, bidding_type, tender_type, bidding_system, tender_closing_date_time, date_time_of_uploading_tender, pre_bid_conference_date_time, advertised_value, earnest_money, contract_type = getpdfdata()

                try:
                    # Calculate due_days
                    closing_datetime = datetime.datetime.strptime(tender_closing_date_time, '%d/%m/%Y %H:%M')
                    uploading_datetime = datetime.datetime.strptime(date_time_of_uploading_tender, '%d/%m/%Y %H:%M')
                    due_days = (closing_datetime - uploading_datetime).days
                except ValueError as e:
                    due_days = " " 
                    pass

                worksheet1.write(k, 0, zone)
                worksheet1.write(k, 1, dept_rly)
                worksheet1.write(k, 2, tender_no)
                worksheet1.write(k, 3, name_of_work)
                worksheet1.write(k, 4, tender_type)
                worksheet1.write(k, 5, tender_closing_date_time)
                worksheet1.write(k, 6, due_days)
                worksheet1.write(k, 7, advertised_value)
                worksheet1.write(k, 8, pdf_url)
                worksheet1.write(k, 9, bidding_type)
                worksheet1.write(k, 10, bidding_system)
                worksheet1.write(k, 11, date_time_of_uploading_tender)
                worksheet1.write(k, 12, pre_bid_conference_date_time)
                worksheet1.write(k, 13, earnest_money)
                worksheet1.write(k, 14, contract_type)

                # Switch back to the initial window
                _close_child_windows(driver, initial_handle)

                if k == tender_count:
                    last_tender = True
                else:
                    last_tender = False

            print("\n")

            if last_tender == True:
                break
            else:

                try:
                    xpath = f"//a[text()='{cnt + 1}']"
                    for attempt in range(3):
                        try:
                            # Wait up to 5 seconds for the element to be clickable
                            element = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, xpath))
                            )
                            element.click()
                            print(f"Successfully clicked page {cnt + 1} on attempt {attempt + 1}")
                            time.sleep(5)
                            break  # Success!
                        except Exception as e:
                            print(f"Attempt {attempt + 1} failed to click page {cnt + 1}: {e}")
                            time.sleep(2)
                    else:
                        print(f"Failed to click page {cnt + 1} after 3 attempts.")

                except Exception as e:
                    print(f"Exception while trying to click page {cnt + 1}: {e}")

            if i % 10 == 0:
                print("\n")
                try:
                    # driver.find_element(By.XPATH, f"//a[font[text()='next']]").click()
                    xpath = "//a[font[text()='next']]"
                    element = driver.find_element(By.XPATH, xpath)
                    element.click()

                except Exception as e:
                    print(f"Element with text 'next' not found")
                    break

            cnt += 1

        # Close the workbook and print a message
        workbook.close()
        print("Zone data Saved.")

    return True



# extract message from adb device connected
def get_sms_message():
    message = ""
    device_serial = get_current_device_serial()
    command = f'adb -s {device_serial} shell content query --uri content://sms/inbox'
    try:
        output = subprocess.check_output(command, shell=True, encoding='utf-8').strip()
        lines = output.split('\n')
        # print(lines)
        for line in lines:
            # Extract the date from the message
            match_date = re.search(r'date=(\d+)', line)
            if match_date:
                timestamp = int(match_date.group(1)) / 1000  # Convert from milliseconds to seconds
                message_date = datetime.datetime.fromtimestamp(timestamp).date()
                # Compare the message date with today's date
                if message_date == datetime.datetime.today().date():  # Use datetime.today() instead of datetime.date.today()
                    # print(line) 
                    if 'IREPS' in line:
                        match_otp = re.search(r'body=(\d{6})', line)
                        if match_otp:
                            six_digits = match_otp.group(1)
                            print(f"OTP: {six_digits}")

                            # print(type(message_date))
                            # countdown_timer(10)

                            # Read the JSON file
                            with open(config_file_path, 'r') as file:
                                config_data = json.load(file)

                            # Update the OTP date and OTP
                            config_data['otp_date'] = message_date.strftime("%Y-%m-%d")
                            config_data['otp'] = six_digits

                            # Write the updated data back to the file
                            with open(config_file_path, 'w') as file:
                                json.dump(config_data, file, indent=4)

                            # with open(otp_full_path, "w") as file:
                            #     file.write(f"Date: {message_date}\n")
                            #     file.write(f"OTP: {six_digits}\n")
                            return False
                        else:
                            print("Pattern not found.")
                    else:
                        message = "Messages not yet received; retring to access the OTP"
        print(message)               
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return True




# generate OTP
def generate_otp(driver, mobile_no):
    driver.refresh()
    time.sleep(3)
    
    # print("Current Mobile No. :", mobile_no)
    driver, Verification_code = get_verification(driver)
    # mobile_no = input("Enter 10 digit Mobile No: ")
    driver.execute_script("document.getElementById('mobileNo').value='" + mobile_no + "'")

    driver.execute_script("document.getElementById('verification').value='" + Verification_code + "'")
    

    driver.find_element("xpath", "//input[@value='Get OTP']").click()
    time.sleep(3)

    try:
        # Check if an alert is present
        alert = driver.switch_to.alert
        print("Alert Text:", alert.text)
        if alert.text == "you have entered wrong verification code.":
            alert.accept()
            generate_otp(driver, mobile_no)

        alert.accept()  # Close the alert (Accept/Dismiss)
    except NoAlertPresentException:
        print("No alert present after clicking 'Get OTP'")
    return driver




def _create_playwright_driver():
    playwright_handle = sync_playwright().start()
    pw_browser = playwright_handle.chromium.launch(
        headless=(browser == "0"),
        args=["--disable-application-cache", "--ignore-certificate-errors"],
    )
    context = pw_browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    driver = PlaywrightDriver(page, context, pw_browser, playwright_handle)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(10)
    return driver


def _ensure_otp_ready(driver, mobile_no):
    """Generate the daily OTP only once when organization workers run in parallel."""
    if is_otp_valid():
        return

    with _otp_lock:
        if is_otp_valid():
            return
        generate_otp(driver, mobile_no)
        countdown_timer("generate_otp", 60)

        while get_sms_message():
            countdown_timer("get_sms_message", 20)
            get_sms_message()


def tenders_main(org_number, org_name, mobile_no, program_files_dir):
    mail_triger = False
    driver = None
    _thread_local.tender_pdf_file_path = os.path.join(
        temp_dir_path,
        f"tender_{_safe_filename(org_number)}_{_safe_filename(org_name)}_{threading.get_ident()}.pdf",
    )

    # org_number, org_name, mobile_no, otp_file_location, program_file_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[4]
    # print(org_number, org_name, mobile_no, otp_file_location)

    try:
        driver = _create_playwright_driver()

        # Open a website
        # Open the URL and wait for the page title to be "IREPS - Guest Login"
        url = "https://www.ireps.gov.in/epsn/anonymSearch.do"

        while True:
            try:
                driver.get(url)
                break # break the loop if no exception occurs
            except Exception as e:
                print(f"{url} - url exception") # - {e}") # print the exception message
                print("Retrying...") # print a retry message
                time.sleep(2)

        driver = is_under_maintenance(driver, url)
        print("Current Mobile NO. ", mobile_no)

        _ensure_otp_ready(driver, mobile_no)
        driver = login(driver, mobile_no)
        mail_triger = tenders(driver, org_number, org_name, program_files_dir)
        print(f"\n\nExeting.... From {org_name}.\n\n")
        return mail_triger
    finally:
        if driver is not None:
            driver.close()
        try:
            if os.path.exists(_active_pdf_path()):
                os.remove(_active_pdf_path())
        except Exception:
            pass


def merge_xlsx_files_in_folders(folders, output_directory, program_file_dir):
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        print(f"Folder '{output_directory}' created successfully.")

    b = datetime.datetime.now()
    merged_data = pd.DataFrame()

    for folder_name in folders:
        folder_path = os.path.join(program_file_dir, folder_name[1])  # Replace 'path_to_root_folder' with the actual root folder path

        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            files = os.listdir(folder_path)

            for file in files:
                if file.endswith('.xlsx'):
                    file_path = os.path.join(folder_path, file)
                    data = pd.read_excel(file_path)

                    # Filter out columns that are all-NA
                    data = data.dropna(how='all', axis=1)

                    # Add the current date to the data
                    b = datetime.datetime.now()
                    data['Get Date'] = b.strftime("%d/%m/%Y")

                    # Concatenate the filtered data
                    merged_data = pd.concat([merged_data, data], ignore_index=True)

    # Create the timestamp for the filename
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    # Output file path and name
    output_filename = f"merged_IREPS_{timestamp}.xlsx"
    output_file_path = os.path.join(output_directory, output_filename)

    # Save the merged data to the output file
    merged_data.to_excel(output_file_path, index=False)

    return output_file_path

# # This function is use to merge xlsx files by first argument is (list of tuples)
# def merge_xlsx_files_in_folders(folders, output_directory, program_file_dir):
#     if not os.path.exists(output_directory):
#         os.makedirs(output_directory)
#         print(f"Folder '{output_directory}' created successfully.")

#     b = datetime.datetime.now()
#     merged_data = pd.DataFrame()

#     for folder_name in folders:
#         folder_path = os.path.join(program_files_dir, folder_name[1])  # Replace 'path_to_root_folder' with the actual root folder path
        
#         # Check if the folder exists before attempting to process it
#         if os.path.exists(folder_path) and os.path.isdir(folder_path):
#             files = os.listdir(folder_path)

#             for file in files:
#                 if file.endswith('.xlsx'):
#                     file_path = os.path.join(folder_path, file)
#                     data = pd.read_excel(file_path)
#                     b = datetime.datetime.now()
#                     data['Get Date'] = b.strftime("%d/%m/%Y")
#                     merged_data = pd.concat([merged_data, data], ignore_index=True)

#         # else:
#         #     # Folder not found, so skip this iteration
#         #     print(f"Folder not found: {folder_path}. Skipping.")

#     # Create the timestamp for the filename
#     timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

#     # Output file path and name
#     output_filename = f"merged_IREPS_{timestamp}.xlsx"
#     output_file_path = os.path.join(output_directory, output_filename)

#     # Save the merged data to the output file
#     merged_data.to_excel(output_file_path, index=False)

#     return output_file_path









# # Load dump location from JSON file
# def load_email_flag():
#     try:
#         with open(config_file_path, "r") as file:
#             data = json.load(file)
#             return data.get("email_flag")
#     except FileNotFoundError:
#         return None







# smtp send status 
def send_mail(program_file_dir, all_email_ids):
    # Check if read_email_ids list has at least one item
    
    if all_email_ids:
        sender_email = "tenderautomation@royalconstruct.in"
        receiver_emails = all_email_ids # ["am7059141480@gmail.com", "vmaskara@royalconstruct.com"] 
        subject = "IREPS Tender Scraping Report"

        notification_text = "This is an automated notification to inform you that the IREPS tender scraping process has been completed. please verify the results \n\n"

        # Gather system information
        system_info = (
            f"System: {platform.system()}\n"
            f"Hostname: {socket.gethostname()}\n"
            f"IP Address: {socket.gethostbyname(socket.gethostname())}\n"
            f"Working Directory: {os.getcwd()}\n"
            f"Windows Version: {platform.win32_ver()[1]}\n"
        )
        # Convert dictionary to JSON format
        # json_data = json.dumps(exception_data_Dictionary, indent=4)

        # Concatenate the notification text, system information, and json data
        # email_body = f"{notification_text}\n{system_info}\n\nLog Data:\n{json_data}"
        email_body = f"{notification_text}\n{system_info}"

        # # Remove brackets from JSON data
        # json_object = json.loads(json_data)
        # if isinstance(json_object, list):
        #     json_data = json_object[0]

        # Create a MIMEText object
        msg = MIMEMultipart()
        msg.attach(MIMEText(email_body))

        # Set the sender and recipients
        msg['From'] = sender_email
        msg['To'] = ", ".join(receiver_emails)
        msg['Subject'] = subject

        # # Attach the log file if requested
        # if attach_log:
        #     if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0:
        #         with open(log_file_path, "rb") as attachment:
        #             part = MIMEBase("application", "octet-stream")
        #             part.set_payload((attachment).read())
        #             encoders.encode_base64(part)
        #             part.add_header("Content-Disposition", "attachment; filename= %s" % log_file_path)
        #             msg.attach(part)
        #     else:
        #         print(f"The file {log_file_path} is empty or does not exist. Not attaching to the email.")
        #         return

        # Attach the first .xlsx file found in the specified folder
        xlsx_folder = program_files_dir

        # List all files in the folder
        files_in_folder = os.listdir(xlsx_folder)

        # Find the first .xlsx file
        for filename in files_in_folder:
            if filename.endswith(".xlsx"):
                xlsx_file_path = os.path.join(xlsx_folder, filename)
                with open(xlsx_file_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload((attachment).read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={filename}")
                    msg.attach(part)
                break  # Attach the first .xlsx file found 

        # Establish a connection to the SMTP server
        smtp_server = "smtp.office365.com"
        port = 587

        username = "tenderautomation@royalconstruct.in"
        password = "Auto@2023"

        # Start the connection to the SMTP server
        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(username, password)

        # Send the email
        server.sendmail(sender_email, receiver_emails, msg.as_string())

        # Close the connection
        server.quit()

        print("\nEmail sent successfully!")
        pass







class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, text):
        for file in self.files:
            file.write(text)

    def flush(self):
        for file in self.files:
            try:
                file.flush()
            except AttributeError:
                pass  # Ignore AttributeError when file is closed



def log_to_file(filename):
    # Create a filename based on current date and time
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_filename = f"{filename}_{timestamp}.txt"
    full_filename = os.path.join(script_dir_path, program_files_dir, "consolelog", new_filename)
    # print(full_filename)
    # time.sleep(1000)
    packge = packaging()
    

    # Open the log file in append mode for regular output
    log_file = open(full_filename, 'a')

    # Redirect stdout to the log file and console simultaneously
    sys.stdout = Tee(sys.stdout, log_file)

    try:

            
        # Your main script logic goes here
        print(f"Starting script execution at {timestamp}\n")

        # Record the start time
        start_time = time.time()








        def f2():
            


            # opening message 
            print("\n|-----| Welcome to the IREPS Scraping system! |-----|\n")


            # # Read the JSON file & Update the email_flag
            # with open(config_file_path, 'r') as file:
            #     config_data = json.load(file)
            # config_data['email_flag'] = "False"
            # # config_data['otp_file_location'] = config_file_path

            # # Write the updated data back to the file
            # with open(config_file_path, 'w') as file:
            #     json.dump(config_data, file, indent=4)

            # Deleting xlsx files
            delete_xlsx_files(program_files_dir)


            # Deleting each Folder by the name of Orgination from "Program_Files (ireps_tender_scraping)"
            for orginazation in organizations:
                file_path = os.path.join(script_dir_path, program_files_dir, orginazation[1]) 
                delete_folder(file_path)



            os.makedirs(temp_dir_path, exist_ok=True)

            if adb_value == "1":
                subprocess.check_output(['adb', 'connect', adb_device_ip]).decode('utf-8').splitlines()
                adb = is_android_device_connected(log_file)
                if adb == False:
                    message = "Please connect an Android device with USB debugging enabled."
                    subject = "IREPS No Android device found."
                    no_adb_mail(subject, message, receiver_emailids)
            else:
                adb = True
            
            mail_triger_main = False
            if adb:
                # Run one Playwright browser context per organization in parallel.
                max_workers = int(data.get("max_org_workers", min(4, max(1, len(organizations)))))
                max_workers = max(1, min(max_workers, max(1, len(organizations))))
                print(f"\nStarting organization scraping with {max_workers} worker thread(s).")

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="IREPSOrg") as executor:
                    future_to_org = {
                        executor.submit(tenders_main, org_number, org_name, mobile_no, program_files_dir): (org_number, org_name)
                        for org_number, org_name in organizations
                    }

                    for future in concurrent.futures.as_completed(future_to_org):
                        org_number, org_name = future_to_org[future]
                        try:
                            org_mail_trigger = future.result()
                            mail_triger_main = mail_triger_main or bool(org_mail_trigger)
                            print(f"\nCompleted Orginazation. {org_number}: {org_name}")
                        except Exception as exc:
                            print(f"\nOrginazation failed. {org_number}: {org_name} - {exc}")
                    # subprocess.run([sys.executable, "Tender.py", org_number, org_name, mobile_no, otp_file_location, program_files_dir])
                    # subprocess.run(["Tender.exe", org_number, org_name, mobile_no, otp_file_location, program_file_dir])


            # master xlsx output directory
            output_directory1 = dump_location  # Replace with the first output directory path
            output_directory2 = program_files_dir   # Replace with the second output directory path
            # creating master xlsx
            output_file_path = merge_xlsx_files_in_folders(organizations, output_directory1, program_files_dir)
            print("Master xlsx saved in ", output_file_path)
            time.sleep(2)
            output_file_path2 = merge_xlsx_files_in_folders(organizations, output_directory2, program_files_dir)
            print("Master xlsx saved in ", output_file_path2)
            time.sleep(2)




            # Final E-Mail with Master xlsx and (log file if exist)
            # mail_triger = load_email_flag()
            # if mail_triger == "True":
            #     if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0:
            #         print(program_file_dir, all_email_ids, log_file_path)
            #         send_mail(program_file_dir, all_email_ids, log_file_path, attach_log=True)
            #     else:
            #         print(program_file_dir, all_email_ids, log_file_path)
            #         send_mail(program_file_dir, all_email_ids, log_file_path, attach_log=False)

            if mail_triger_main == True:
                print(program_files_dir, receiver_emailids)
                send_mail(program_files_dir, receiver_emailids)








        def f1():
            for _ in range(3):
                if check_internet_connection():
                    f2()
                    countdown_timer("Exeting in ... ", 10)
                    break
            sys.exit()  # This will exit the Python interpreter

        f1()



        # Record the end time
        end_time = time.time()
        # Calculate the total time taken
        total_time = end_time - start_time
        # Convert seconds to hours, minutes, and seconds
        hours, remainder = divmod(total_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"Total time taken by the Program: {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds")







        print("Exiting... from tenders download program.")    
        # Example: Simulate an exception
        # Uncomment the following line to simulate an exception
        # raise ValueError("This is a simulated exception")

        print("\nScript execution completed.")

    except Exception as e:
        # Print the exception details to both console and error log file
        error_message = f"Exception occurred during script execution: {e}"
        print(error_message, file=sys.stderr)
        log_file.write(error_message + "\n")  # Write the error message to log file

    finally:
        # Restore the original stdout
        sys.stdout = sys.__stdout__  # Restore original stdout
        log_file.close()              # Close the log file

if __name__ == "__main__":
    create_folder_if_not_exists(os.path.join(script_dir_path, program_files_dir, "consolelog"))
    log_to_file("ireps-tenders-output_log")
    sys.exit()