"""
# cd C:\\Alan\\ODD\\oddapp\\oddapp

python -m venv venv
.\\venv\\scripts\\activate

pip install azure-servicebus sendgrid
pip install azure.identity azure.storage.blob azure.keyvault.secrets fastapi
pip install uvicorn python-dotenv
pip install python-multipart
pip install fastapi_utils typing_inspect
python ./app/main.py

"""

import uvicorn
import asyncio
import time
import logging
import sys
import os
import json
from io import StringIO


from fastapi import FastAPI, BackgroundTasks, Request, Form
from fastapi.concurrency import run_in_threadpool
from fastapi_utils.tasks import repeat_every
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage

from azure.storage.blob import BlobServiceClient

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from dotenv import load_dotenv

# Load environment variables
load_dotenv()



# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVICE_BUS_CONNECTION_STRING = os.environ['SERVICE_BUS_CONNECTION_STRING'] 
QUEUE_NAME = os.environ['QUEUE_NAME']
SENDGRID_API_KEY = os.environ['SENDGRID_API_KEY'] 

BLOB_CONNECTION_STRING = os.environ['BLOB_CONNECTION_STRING'] 
BLOB_CONTAINER_NAME = os.environ['BLOB_CONTAINER_NAME'] 
BLOB_NAME = os.environ['BLOB_NAME'] 
SENDGRID_EMAIL = os.environ['SENDGRID_EMAIL'] 



# Initialize the FastAPI application
app = FastAPI()



# Initialize the Service Bus client outside the route functions
service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

def log_to_blob(message: str):
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob="log.txt")
    blob_contents = message + "\n"
    log_to_blob(f"Log to blob {blob_contents}")
    blob_client.upload_blob(blob_contents, blob_type="AppendBlob", overwrite=True)


# Function to send an email using SendGrid
def send_email(to_email: str, subject: str, content: str):
    message = Mail(
        from_email=SENDGRID_EMAIL, # Use a verified sender email
        to_emails=to_email,
        subject=subject,
        plain_text_content=content
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {to_email} with status code {response.status_code}")
        log_to_blob(f"Email sent to {to_email} with status code {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        log_to_blob(f"Error sending email to {to_email}: {str(e)}")

# Function to process messages from the Service Bus queue
async def process_messages():
    service_bus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
    with service_bus_client:
        receiver = service_bus_client.get_queue_receiver(queue_name=QUEUE_NAME)
        with receiver:
            # received_msgs = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            try:
                while True:
                    messages = receiver.receive_messages(max_message_count=10, max_wait_time=5)
                    tasks = []
                    
                    for msg in messages:
                        email_data = json.loads(str(msg))
                        tasks.append(send_email(email_data['to_email'], email_data['subject'], email_data['content']))
                        receiver.complete_message(msg)  # Mark the message as processed

                    if tasks:
                        asyncio.gather(*tasks)  # Send all emails concurrently

                    # asyncio.sleep(1)  # Optional: Wait before checking for new messages again
            finally:
                # await receiver.__aexit__(None, None, None)  # Ensure the receiver is properly exited
                print("prob here")
                return

def cpu_bound_looping_task():
    while True:
        print("CPU-bound looping background task running...")
        # Simulate CPU-bound work
        asyncio.run(process_messages())
        # process_messages()
        time.sleep(15) 

@app.on_event("startup")
async def startup_event():
    # Run the CPU-bound task in a separate thread
    asyncio.create_task(run_in_threadpool(cpu_bound_looping_task))


@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = '''
    <html>
        <head>
            <title>Send Email</title>
        </head>
        <body>
            <h1>Send Email Information</h1>
            <form action="/send_email" method="post">
                <input type="email" name="to_email" placeholder="Recipient Email" required>
                <input type="text" name="subject" placeholder="Email Subject" required>
                <textarea name="content" placeholder="Email Content" required></textarea>
                <button type="submit">Send Email</button>
            </form>
        </body>
    </html>
    '''
    return HTMLResponse(content=html_content)

# Route to handle sending email requests

@app.post("/send_email")
async def send_email_endpoint(request: Request):
    form_data = await request.form()
    to_email = form_data.get('to_email')
    subject = form_data.get('subject')
    content = form_data.get('content')

    # Prepare the message and send it to the queue
    email_data = {
        'to_email': to_email,
        'subject': subject,
        'content': content
    }

    with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
        with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            message = ServiceBusMessage(json.dumps(email_data))
            sender.send_messages(message) # Send the message to the queue
            
    return {"message": "Email request submitted!"}


""" # works however blocks main thread

async def periodic_task():
    while True:
        print("Running periodic task...")
        asyncio.create_task(process_messages())
        await asyncio.sleep(5)  # Wait for 5 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_task())
    # asyncio.create_task(process_messages())


"""

# # Main entry point to run the FastAPI application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
