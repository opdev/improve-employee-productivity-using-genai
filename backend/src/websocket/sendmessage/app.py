import json
import boto3
import os
import time
import base64
from botocore.exceptions import ClientError
from langchain_openai import ChatOpenAI

def get_images_from_s3_as_base64(image_keys):
    """Download images from S3 and convert to base64."""
    s3 = boto3.client('s3')
    image_data_list = []
    for key in image_keys:
        try:
            response = s3.get_object(Bucket=os.environ['IMAGE_UPLOAD_BUCKET'], Key=key)
            image_data = response['Body'].read()
            image_data_list.append(base64.b64encode(image_data).decode('utf-8'))
        except Exception as e:
            print(f"Error getting object {key}.", str(e))
            image_data_list.append(None)
    return image_data_list

def handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ.get('DYNAMODB_TABLE'))

    # Extract information from the event
    domain_name = event['requestContext']['domainName']
    stage = event['requestContext']['stage']
    connection_id = event['requestContext']['connectionId']

    # Initialize the API Gateway Management API
    api_gateway_management_api = boto3.client('apigatewaymanagementapi', endpoint_url=f'https://{domain_name}/{stage}')

    # Parse the incoming message
    body = json.loads(event['body'])
    action = body.get('action')
    data = body.get('data')

    # Retrieve optional parameters or set default values
    max_tokens_to_sample = body.get('max_tokens_to_sample', 4000)
    temperature = body.get('temperature', 0)
    modelId = body.get('modelId', "llama3")  # Use Llama3 model ID
    top_k = body.get('top_k', 250)
    top_p = body.get('top_p', 0.999)

    # Extract necessary information
    email = event['requestContext']['authorizer']['principalId']
    source_ip = event['requestContext']['identity']['sourceIp']
    request_id = event['requestContext']['requestId']
    user_agent = event['requestContext']['identity']['userAgent']
    prompt_data = body.get('data', '')
    current_timestamp = str(int(time.time()))

    # Retrieves 'system' if provided, else None
    system_prompt = body.get('system', None)

    # Extract image keys from the event body
    image_s3_keys = body.get('imageS3Keys', [])

    # Only attempt to process the image if provided
    if image_s3_keys:
        # Make sure the list does not exceed 6 items
        image_s3_keys = image_s3_keys[:6]

        images_base64 = get_images_from_s3_as_base64(image_s3_keys)

    # Initialize the Llama3 model with ChatOpenAI via LangChain
    chat_model = ChatOpenAI(
        model_id="llama3",  # Use Llama3 model
        temperature=temperature,
        max_tokens=max_tokens_to_sample,
        top_k=top_k,
        top_p=top_p,
        base_url="https://llama3-genai-doc-summarization.apps.osai.openshiftpartnerlabs.com/v1",  # Replace with actual base URL
        api_key="YOUR_API_KEY"  # Replace with actual API key
    )

    # Prepare the request for Llama3
    if action == 'sendmessage':
        # Prepare the request for the Llama3 model, including the optional image
        messages_content = [
            {
                "type": "text",
                "text": data
            }
        ]

        if image_s3_keys:
            for image_base64 in images_base64:
                messages_content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}
                })

        message = [
            {
                "role": "user",
                "content": messages_content
            }
        ]

        # Prepare the payload for the Llama3 model
        llama_request_dict = {
            "messages": message,
            "max_tokens": max_tokens_to_sample,
            "temperature": temperature,
            "top_k": top_k,
            "top_p": top_p
        }

        # Only add 'system' to payload if it was provided
        if system_prompt:
            llama_request_dict["system"] = system_prompt

        # Invoke the Llama3 model and handle the response
        try:
            # Generate a response using the Llama3 model
            response = chat_model.generate(
                prompt=json.dumps(llama_request_dict)
            )

            # Send the response to the client
            api_gateway_management_api.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({"messages": response})
            )

            # Prepare the item to insert into DynamoDB
            item_to_insert = {
                'email': email,
                'timestamp': current_timestamp,
                'requestId': request_id,
                'promptData': prompt_data,
                'modelId': modelId,
                'sourceIp': source_ip,
                'requestBody': json.dumps(body),
                'userAgent': user_agent,
                'completion': response
            }

            # Add the imageS3Key to the item if it exists
            if image_s3_keys:
                item_to_insert['imageS3Keys'] = image_s3_keys

            if system_prompt:
                item_to_insert['systemPrompt'] = system_prompt

            # Insert the data into DynamoDB
            table.put_item(Item=item_to_insert)

            # After sending the response, send the end-of-message signal
            api_gateway_management_api.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps({"endOfMessage": True})
            )

        except ClientError as error:
            error_message = error.response['Error']['Message']
            print(f"Error: {error_message}")

            # Send the error message to the client
            errorMessage = {
                'action': 'error',
                'error': error_message
            }
            api_gateway_management_api.post_to_connection(
                ConnectionId=event['requestContext']['connectionId'],
                Data=json.dumps(errorMessage)
            )

            return {
                'statusCode': 500,
                'body': f'Error: {error_message}'
            }

    return {
        'statusCode': 200,
        'body': 'Message processed'
    }
