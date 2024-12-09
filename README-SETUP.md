# Employee Productivity GenAI Assistant Demo

Clone the repository [Employee Producitivty Application](https://github.com/opdev/improve-employee-productivity-using-genai/tree/demo)

# Setting up Hugging Face & MinIO

## Prerequisites

### Set up Hugging Face & Access to Meta Llama models
Set up a [Hugging Face](https://huggingface.co/) account and request access to the [Meta Llama models](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct).
We will be using the `meta-llama/Llama-3.1-8B-Instruct` specifically but once you've gained access to the gated repo, you will gain access to all the models with meta-llama repository.
You will need to put in your information and agree to the terms, usage, and licensing agreement and wait for your request to be approved to gain access to the repository.
It may take a while, but you can check the status of your request in `Profile > Settings > Gated Repositories`

Create an access token and save it for later to be able to make requests to the llama model.
* Select your profile image in the top right corner and at the bottom select `Access Token`
* Select `+Create Access Token`
* For the purpose of this project, all you need is a "Read" type access token
* Give it any name and select `Create Token`

### Set up RHOAI & NVIDIA GPU

Before you can serve a model in Red Hat OpenShift AI, you will need to install RHOAI and enable NVIDIA GPU by following these links:
* [Red Hat OpenShift AI installation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/2.13/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-and-deploying-openshift-ai_install)
* [Enable NVIDIA GPU](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/2.13/html/installing_and_uninstalling_openshift_ai_self-managed/enabling-nvidia-gpus_install#enabling-nvidia-gpus_install)

This project uses `MinIO` to store the model:
  * _Install the `oc` client to use MinIO for model storage_


## Quickstart

Open up `Red Hat OpenShift AI` by selecting it from OpenShift Application Launcher.
This will open up `Red Hat OpenShift AI` in a new tab.

Create a Data Science project in `Red Hat OpenShift AI` window.

### Setup MinIO
To setup MinIO, for storing the model, execute the following commands in a terminal/console:
```
# Login to OpenShift (if not already logged in)
oc login --token=<OCP_TOKEN>

# Install MinIO
MINIO_USER=<USERNAME> \
   MINIO_PASSWORD="<PASSWORD>" \
   envsubst < minio-setup/minio-setup.yml | \
   oc apply -f - -n <DATA_SCIENCE_PROJECT_CREATED_IN_PREVIOUS_STEP>
```

* _Set `<USERNAME>` and `<PASSWORD>` to some valid values, in the above command, before executing it_


Once MinIO is setup, you can access it within your project. The yaml that was applied above creates these two routes:
* `minio-ui` - for accessing the MinIO UI
* `minio-api` - for API access to MinIO
  * Take note of the `minio-api` route location as that will be needed in next section.


### Create workbench
To use RHOAI for this project, you need to create a workbench first. In the newly created data science project, create a new Workbench by clicking `Create workbench` button in the `Workbenches` tab.

When creating the workbench, add the following environment variables:
* AWS_ACCESS_KEY_ID
  * MinIO user name
* AWS_SECRET_ACCESS_KEY
  * MinIO password
* AWS_S3_ENDPOINT
  * `minio-api` route location
* AWS_S3_BUCKET
  * This bucket should _either be existing or will be created_ by one of the
    Jupyter notebooks to upload the model
* AWS_DEFAULT_REGION
  * Set it to `us-east-1`

  _The environment variables can be added one by one, or all together by uploading a secret yaml file_

    ```
    # Save your ENV values as base64 and save it in the secret yaml file located at workbench_env.yaml
    echo -n 'YOUR_AWS_ACCESS_KEY_ID' | base64
    echo -n 'YOUR_AWS_SECRET_ACCESS_KEY' | base64
    echo -n 'YOUR_AWS_DEFAULT_REGION' | base64
    echo -n 'YOUR_AWS_S3_ENDPOINT' | base64
    echo -n 'YOUR_AWS_S3_BUCKET' | base64
    ```

Use the following values for other fields:
* _Notebook image_:
  * Image selection: **PyTorch**
  * Version selection: **2024.1**
* _Deployment size_:
  * Container size: **Medium**
  * Accelerator: **NVIDIA GPU**
  * Number of accelerators: **1**
* _Cluster storage_: **50GB**

Create the workbench with above settings.


### Create Data connection
Create a new data connection that can be used by the init-container (`storage-initializer`) to fetch the model uploaded in next step when deploying the model.

To create a Data connection, use the following steps:
* Click on `Add data connection` button in the  `Data connections` tab in your newly created project
* Use the following values for this data connection:
  * _Name_: `minio`
  * _Access key_: value specified for `AWS_ACCESS_KEY_ID` field in `Create Workbench` section
  * _Secret key_: value specified for `AWS_SECRET_ACCESS_KEY` field in `Create Workbench` section
  * _Endpoint_: value specified for `AWS_S3_ENDPOINT` field in `Create Workbench` section
  * _Access key_: value specified for `AWS_DEFAULT_REGION` field in `Create Workbench` section
  * _Bucket_: value specified for `AWS_S3_BUCKET` field in `Create Workbench` section
* Create the data connection by clicking on `Add data connection` button


### Add Serving runtime
To run the Llama3.1 model in RHOAI, you will need to duplicate the `vLLM ServingRuntime for KServe` Serving runtime and edit it as well.

Follow these steps for duplicating and editing the above mentioned Serving runtime:
* Expand `Settings` sidebar menu in RHOAI
* Click on `Serving runtimes` in the expanded sidebar menu
* Click the three dots at the end of `vLLM ServingRuntime for KServe` Serving runtime and select `Duplicate`
* In the duplicated runtime:
  * Change the following to make them unique for your use-case:
    * `metadata.annotations.openshift.io/display-name`
    * `metadata.name`
  * Add the following argument to `spec.containers.args` property:
    * `--max_model_len=4096`
      * _If you do not set the above argument then you will run into the following error when starting the model_:
        ```
        ValueError: The model's max seq len (131072) is larger than the maximum number of tokens that can be stored in KV cache (28560). Try increasing `gpu_memory_utilization` or decreasing `max_model_len` when initializing the engine.
        ```
* Click on `Create` button to create this new Serving runtime

_You can read more about Model serving [here](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/2-latest/html/serving_models/about-model-serving_about-model-serving)_


### Deploy model
Once the initial notebook has run successfully and the data connection is created, you can deploy the model by following these steps:
* In the RHOAI tab, select `Models` tab (_for your newly created project_) and click on `Deploy model` button
* Fill in the following fields as described below:
  * _Model name_: **<PROVIDE_a_name_for_the_model>**
  * _Serving runtime_: **NAME YOU GAVE TO THE DUPLICATED SERVING RUNTIME**
  * _Model framework_: **vLLM**
  * _Model server size_: **Small**
  * _Accelerator_: **NVIDIA GPU**
  * _Model route_:
    * _If you want to access this model endpoint from outside the cluster_, make sure to check the `Make deployed models available through an external route` checkbox. By default the model endpoint is only available as an _internal service_.
  * _Model location_: Select **Existing data connection** option
    * _Name_: **Name of data connection created in previous step**
    * _Path_: **models**
* Click on `Deploy` to deploy this model

Copy the `inference endpoint` once the model is deployed successfully (_it will take a few minutes to deploy the model_).

# Setting up AWS Employee Productivity Application

1. Clone the repo [Employee Producitivty Application](https://github.com/opdev/improve-employee-productivity-using-genai/tree/demo)

2. Follow along with the README and install all the require prerequisites.


3. In the the app.py, located in **/improve-employee-productivity-using-genai/backend/src/websocket/chat/app.py**

    Change the ChatOpenAI model base_url to the inference endpoint you saved in the step above

    ```
     # Configure the ChatOpenAI model
        chat_model = ChatOpenAI(
            model = "llama3",
            temperature = "0.1",
            base_url = "YOUR_ENDPOINT",
            api_key = "YOUR_API_KEY",
        )
    ```
4. Deploy your application. For this exact project we will deploy it locally.
    Run the command in your terminal in the project folder
    ```
    ./deploy.sh --region=your-aws-region --email=your-email
    ```
5. Follow the link provided. Login in with your credentials and create new credentials if it is your first time logging on. Navigate to the **Chat** tab and test away.

