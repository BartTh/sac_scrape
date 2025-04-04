import time
import random
import smtplib
import datetime
import os
import backoff

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv


huts = {'Chanrion': 'https://www.hut-reservation.org/reservation/book-hut/379/wizard',
        'Vignettes': 'https://www.hut-reservation.org/reservation/book-hut/226/wizard'}


def send_draft_email(hut, free_places, arrival_date_str, departure_date_str):
    print('Sending email..')
    smtp = smtplib.SMTP('smtp.mail.me.com', 587)
    smtp.starttls()
    smtp.login(os.getenv("USER_NAME"), os.getenv("PW_EMAIL"))

    # Create message
    text = f"""Hi,
    
Places in {hut} ({arrival_date_str} - {departure_date_str}): {free_places}

Book: {huts[hut]}

Best,
    """

    new_message = MIMEMultipart()
    new_message["From"] = os.getenv("USER_NAME")
    new_message["To"] = os.getenv("USER_NAME")
    new_message["Subject"] = f"{hut}: {free_places} places!"
    new_message.attach(MIMEText(text))

    # Fix special characters by setting the same encoding we'll use later to encode the message
    smtp.sendmail(new_message['From'], new_message['To'], new_message.as_string())

    # Cleanup
    smtp.close()


@backoff.on_exception(backoff.expo, Exception, max_tries=3)
def check_availability(arrival_date_str, departure_date_str):
    # Initialize ChromeDriver properly
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    try:
        # Navigate to the SAC login page
        driver.get("https://portal.sac-cas.ch/de/users/sign_in?oauth=true")

        # Wait for the username field to be present and enter email
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.ID, "person_login_identity"))
        ).send_keys(os.getenv("USER_NAME"))

        # Enter password
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "person_login_identity"))
        ).send_keys(os.getenv("PW_SAC"))

        for hut in huts:
            # Navigate to the specific hut's booking page
            driver.get(huts[hut])

            # Wait for the date picker button and click it
            date_picker_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "cy-datePicker__toggle"))
            )
            date_picker_button.click()

            # Select arrival date
            arrival_date = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@data-test='input-arrival-date-reservation']"))
            )
            arrival_date.clear()
            arrival_date.send_keys(arrival_date_str)
            arrival_date.send_keys(Keys.RETURN)

            # Select departure date
            departure_date = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[@data-test='input-departure-date-reservation']"))
            )
            departure_date.clear()
            departure_date.send_keys(departure_date_str)
            departure_date.send_keys(Keys.RETURN)

            # Wait for the table to load and locate the free places value
            free_places_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "td.table_row_places.cdk-column-freePlaces"))
            )

            # Extract the text from the element
            free_places = free_places_element.text.strip()

            print(f"[{datetime.datetime.now()}] [{hut}] Number of free places: {free_places}")

            if int(free_places) > 0:
                send_draft_email(hut, free_places, arrival_date_str, departure_date_str)

    except Exception as e:
        print(f"[{datetime.datetime.now()}] Error occurred: {e}")

    finally:
        # Close the WebDriver
        driver.quit()


load_dotenv()  # loads from .env

# User-defined dates
arrival_date = "18.04.2025"
departure_date = "19.04.2025"

# Run the script every hour
while True:
    check_availability(arrival_date, departure_date)
    interval = random.randint(1800, 3600)  # Random sleep time between 1800 (30m) and 3600s (1h)
    time.sleep(interval)
