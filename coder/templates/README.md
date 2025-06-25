# Pushing Templates to a Coder Instance Using Coder CLI

Follow these steps to push your template directories to your Coder instance:

1. **Install Coder CLI**  
    If you haven't already, install the Coder CLI:  
    ```sh
    brew install coder/coder/coder
    ```

2. **Authenticate with Your Coder Instance**  
    ```sh
    coder login <your-coder-instance-url>
    ```

3. **Navigate to the the Template directory that you want to upload**  
Example:

    ```sh
    cd bootcamp
    ```

4. **Copy Terraform variables example file and update the values**

    ```sh
    cp terraform.tfvars.example terraform.tfvars 
    ```

5. **Upload the Template**  
    ```sh
    coder templates push
    ```

6. **Verify Templates on Coder**  
    Visit your Coder instance dashboard to confirm the templates are available.

> **Note:**  
>  - You can also do this through the Coder Dashboard UI using the steps mentioned [here](https://coder.com/docs/tutorials/template-from-scratch#add-the-template-files-to-coder).
>  - Refer to the [Coder Templates documentation](https://coder.com/docs/admin/templates/creating-templates) for more details.