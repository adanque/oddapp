"""
# cd C:\\Alan\\ODD\\oddapp\\oddapp

python -m venv venv
.\\venv\\scripts\\activate

pip install azure-servicebus sendgrid
pip install azure.identity azure.storage.blob azure.keyvault.secrets fastapi
pip install uvicorn python-dotenv
pip install python-multipart

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

from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
# from app.api import router
# from app.config import settings

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

# Initialize the FastAPI application
# app = FastAPI()

# Initialize Azure Blob Service
blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)

# async def process_messages():
#     while True:
#         print("Running asynchronous background task...")
#         with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
#             with client.get_queue_receiver(queue_name=QUEUE_NAME) as receiver:
#                 for msg in receiver:
#                     email_data = json.loads(str(msg))
#                     send_email(email_data['to_email'], email_data['subject'], email_data['content'])
#                     receiver.complete_message(msg)
#                     log_to_blob(f"Processing ServiceBus Queue to {email_data['to_email']} subject: {email_data['subject']} msg: {str(msg)}")
#         await asyncio.sleep(5) # Wait for 5 seconds asynchronously

# async def process_messages():
#     async with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
#         async with client.get_queue_receiver(queue_name=QUEUE_NAME) as receiver:
#             while True:
#                 messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
#                 tasks = [] # List to hold all email sending tasks
                
#                 for msg in messages:
#                     email_data = json.loads(str(msg))
#                     # Create a task for sending the email and add it to the list
#                     tasks.append(send_email(email_data['to_email'], email_data['subject'], email_data['content']))
#                     log_to_blob(f"Create a task for sending the email and add it to the list")
#                     await receiver.complete_message(msg) # Mark message as processed

#                 if tasks:
#                     await asyncio.gather(*tasks) # Run all email sending tasks concurrently

#                 await asyncio.sleep(1) # Optional: Sleep before checking for more messages

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup event: Create and start the background task
    task = asyncio.create_task(process_messages())
    yield
    # Shutdown event: Cancel the background task
    task.cancel()
    await task # Wait for the task to finish cancelling

async def process_messages():
    servicebus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
    async with servicebus_client.get_queue_receiver(queue_name=QUEUE_NAME) as receiver:
        while True:
            messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
            tasks = [] # List to hold all email sending tasks
            
            for msg in messages:
                email_data = json.loads(str(msg))
                # Create a task for sending the email and add it to the list
                tasks.append(send_email(email_data['to_email'], email_data['subject'], email_data['content']))
                log_to_blob(f"Create a task for sending the email and add it to the list")
                await receiver.complete_message(msg) # Mark message as processed

            if tasks:
                await asyncio.gather(*tasks) # Run all email sending tasks concurrently

            await asyncio.sleep(1) # Optional: Sleep before checking for more messages


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup event: Create and start the background task
#     task = asyncio.create_task(process_messages())
#     yield
#     # Shutdown event: Cancel the background task
#     task.cancel()
#     await task # Wait for the task to finish cancelling

# app = FastAPI()
# app = FastAPI(lifespan=lifespan)

# Function to log messages to Azure Blob Storage
def log_to_blob(message: str):
    blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob="log.txt")
    blob_contents = message + "\n"
    log_to_blob(f"Log to blob {blob_contents}")
    blob_client.upload_blob(blob_contents, blob_type="AppendBlob", overwrite=True)

# Function to send an email
def send_email(to_email: str, subject: str, content: str):
    message = Mail(
        from_email='adanque@cen-gen.com', # Use a verified sender email
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

# Function to send a message to the Service Bus queue
def send_message_to_queue(email_message: str):
    with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
        with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            message = ServiceBusMessage(email_message)
            sender.send_messages(message)
            logger.info(f"Message sent to queue: {email_message}")
            log_to_blob(f"Message sent to queue: {email_message}")

# app = FastAPI(lifespan=lifespan)
app = FastAPI()
# use http://localhost:8000/

# Define the root endpoint with a button to send a message
# @app.get("/", response_class=HTMLResponse)
# async def read_root():
#     html_content = '''
#     <html>
#         <head>
#             <title>Send Email</title>
#         </head>
#         <body>
#             <h1>Send an Email</h1>
#             <form action="/send_email" method="post">
#                 <input type="text" name="to_email" placeholder="Recipient Email" required>
#                 <input type="text" name="subject" placeholder="Email Subject" required>
#                 <textarea name="content" placeholder="Email Content" required></textarea>
#                 <button type="submit">Send Email</button>
#             </form>
#         </body>
#     </html>
#     '''
#     return HTMLResponse(content=html_content)

# Endpoint to serve the web input form
@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = '''
    <html>
        <head>
            <title>Send Email</title>
        </head>
        <body>
            <h1>Send an Email</h1>
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

# Endpoint to handle sending email and processing queue
# @app.post("/send_email")
# async def send_email_endpoint(request: Request):
#     form_data = await request.form()
#     to_email = form_data.get('to_email')
#     subject = form_data.get('subject')
#     content = form_data.get('content')

#     # Prepare message and send to queue
#     email_data = {
#         'to_email': to_email,
#         'subject': subject,
#         'content': content
#     }
#     send_message_to_queue(json.dumps(email_data))
    
#     return {"message": "Email request submitted!"}





# Endpoint to handle sending email requests
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

    async with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
        async with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            message = ServiceBusMessage(json.dumps(email_data))
            await sender.send_messages(message) # Send the message to the queue
            
    return {"message": "Email request submitted!"}

# Endpoint to handle sending email requests
# @app.post("/send_email")
# async def send_email_endpoint(request: Request):
#     form_data = await request.form()
#     to_email = form_data.get('to_email')
#     subject = form_data.get('subject')
#     content = form_data.get('content')

#     # Prepare the message and send it to the queue
#     email_data = {
#         'to_email': to_email,
#         'subject': subject,
#         'content': content
#     }
#     print(email_data)

#     # async with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as servicebus_client:
#     with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as servicebus_client:        
#         sender = None # Initialize sender to None
#         try:
#             sender = servicebus_client.get_queue_sender(queue_name=QUEUE_NAME)
#             if sender is None:
#                 print("Error: Sender object could not be created.")
#                 return # Exit or handle the error appropriately
            
#             message = ServiceBusMessage(json.dumps(email_data))
#             sender.send_messages(message) # Send the message to the queue
#             # await sender.send_messages(message) # Send the message to the queue
#             log_to_blob(f"Message sent to servicebus_client: {email_data}")

#         finally:
#             if sender: # Only attempt to close if sender is not None
#                 sender.close()
#                 # await sender.close()
#             servicebus_client.close()                
#             # await servicebus_client.close()

#     # servicebus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
#     # # async with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
#     # async with servicebus_client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
#         # try:
#         #     message = ServiceBusMessage(json.dumps(email_data))
#         #     await sender.send_messages(message) # Send the message to the queue
#         #     log_to_blob(f"Message sent to servicebus_client: {email_data}")
#         # finally:
#         #     await sender.close()        
#     return {"message": "Email request submitted!"}



# async def process_messages():
#     servicebus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING)
#     async with servicebus_client.get_queue_receiver(queue_name=QUEUE_NAME) as receiver:
#         while True:
#             messages = await receiver.receive_messages(max_message_count=10, max_wait_time=5)
#             tasks = [] # List to hold all email sending tasks
     

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup event: Create and start the background task
#     task = asyncio.create_task(process_messages())
#     yield
#     # Shutdown event: Cancel the background task
#     task.cancel()
#     await task # Wait for the task to finish cancelling




# Entry point for the application to start the message processing loop
# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(process_messages())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# async def main():
#     # Start the background task
#     task = asyncio.create_task(process_messages())

#     # Configure and run Uvicorn
#     config = uvicorn.Config(app, host="0.0.0.0", port=8000)
#     server = uvicorn.Server(config)

#     # Run Uvicorn within the same event loop
#     await server.serve()

# # If the script is run directly, uncomment this for development
# if __name__ == "__main__":
#     asyncio.run(main())



    # import uvicorn
    # task = asyncio.create_task(process_messages())
    # uvicorn.run(app, host="0.0.0.0", port=8000)

    # while True:
    #     process_messages()  # This will block until a message is available
    #     time.sleep(5)  # Optionally, wait some time before checking again


# # Azure Service Bus setup
# def send_email_notification(email_address, SERVICE_BUS_CONNECTION_STRING):
#     service_bus_connection_string = SERVICE_BUS_CONNECTION_STRING
#     topic_name = "your_topic_name"
#     servicebus_client = ServiceBusClient.from_connection_string(conn_str=service_bus_connection_string)

#     with servicebus_client.get_topic_sender(topic_name) as sender:
#         message = ServiceBusMessage(f"Send email to: {email_address}")
#         sender.send_messages(message)

# # Function to send email using SendGrid
# def send_email(to_email, subject, content):
#     message = Mail(
#         from_email='adanque@cen-gen.com', # Use a verified sender email
#         to_emails=to_email,
#         subject=subject,
#         plain_text_content=content
#     )
#     try:
#         sg = SendGridAPIClient(SENDGRID_API_KEY)
#         response = sg.send(message)
#         return response.status_code
#     except Exception as e:
#         print(f"Error sending email: {str(e)}")
#         return None

# # Function to process message from Azure Service Bus
# def process_message(message):
#     try:
#         email_data = json.loads(str(message))
#         send_email(email_data['to_email'], email_data['subject'], email_data['content'])
#         print("Email sent successfully!")
#     except Exception as e:
#         print(f"Failed to process message: {str(e)}")

# # Function to receive messages from the Service Bus queue
# def receive_messages():
#     with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
#         with client.get_queue_receiver(queue_name=QUEUE_NAME) as receiver:
#             for msg in receiver:
#                 process_message(msg)
#                 receiver.complete_message(msg)

# # Function to send a message to the Service Bus queue
# def send_message(to_email, subject, content):
#     message_data = {
#         'to_email': to_email,
#         'subject': subject,
#         'content': content
#     }
#     message = ServiceBusMessage(json.dumps(message_data))
#     with ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STRING) as client:
#         with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
#             sender.send_messages(message)
#             print("Message sent to Service Bus!")

# # Configure logging to Azure Blob Storage
# class AzureBlobHandler(logging.Handler):
#     def __init__(self, blob_service_client, BLOB_CONTAINER_NAME, BLOB_NAME):
#         super().__init__()
#         self.blob_service_client = blob_service_client
#         self.container_name = BLOB_CONTAINER_NAME
#         self.blob_name = BLOB_NAME
#         self.blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=BLOB_NAME)

#     def emit(self, record):
#         log_entry = self.format(record)
#         self.blob_client.append_block(log_entry.encode('utf-8'))

# def configure_logging(BLOB_CONNECTION_STRING, BLOB_CONTAINER_NAME, BLOB_NAME):
#     blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
#     logger = logging.getLogger("AzureLogger")
#     logger.setLevel(logging.DEBUG)
#     azure_blob_handler = AzureBlobHandler(blob_service_client, BLOB_CONTAINER_NAME, BLOB_NAME)
#     formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#     azure_blob_handler.setFormatter(formatter)
#     logger.addHandler(azure_blob_handler)
#     return logger

# # Redirect print statements to logger
# class PrintToLog:
#     def __init__(self, logger):
#         self.logger = logger
#         self.old_stdout = sys.stdout

#     def write(self, message):
#         if message.strip():
#             self.logger.info(message.strip())

#     def flush(self):
#         pass


# # FastAPI routes
# @app.post("/button-click")
# async def button_click(background_tasks: BackgroundTasks, email: str, SERVICE_BUS_CONNECTION_STRING: str):
#     print(f"Button clicked to send email to: {email}") # This will log to Azure Blob Storage
#     background_tasks.add_task(send_email_notification, email, SERVICE_BUS_CONNECTION_STRING)
#     return {"message": "Email will be sent shortly."}

# # Setup
# def main():
#     # connection_string = "your_connection_string"
#     # container_name = "your_container_name"
#     # blob_name = "your_blob_name.txt"
        


# # blob_connection_string, container_name, blob_name
#     # Configure logger
#     logger = configure_logging(BLOB_CONNECTION_STRING, BLOB_CONTAINER_NAME, BLOB_NAME)

#     # Redirect print() to the logger
#     print_logger = PrintToLog(logger)
#     sys.stdout = print_logger


# # Example usage
# if __name__ == "__main__":
#     # Sending a message to trigger an email
#     send_message('recipient@example.com', 'Hello from Azure!', 'This is a test email sent using Azure Service Bus and SendGrid.')

#     # To listen for and send emails, uncomment and run in a separate process
#     # receive_messages()



# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=settings.ALLOW_ORIGINS,
# #     allow_credentials=True,
# #     allow_methods=['*'],
# #     allow_headers=['*'],
# # )

# # app.include_router(router)

# # @app.head('/health')
# # @app.get('/health')
# # def health_check():
# #     return 'ok'