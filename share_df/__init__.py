import warnings
import pandas as pd
import polars as pl
from typing import Union, List, Optional
import os
import sys
from pathlib import Path

warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

__version__ = "0.1.0"
__all__ = ["pandaBear", "retrieve_cloud_dataframe", "list_cloud_versions"]

def _setup_aws_credentials():
    """
    Interactive setup for AWS credentials.
    Walks the user through the process of creating and configuring AWS credentials.
    
    Returns:
        bool: True if credentials were successfully set up, False otherwise
    """
    from dotenv import load_dotenv, set_key
    load_dotenv()
    
    print("\n🌥️  AWS Cloud Hosting Setup Wizard 🌥️\n")
    print("This wizard will help you set up your AWS credentials for cloud hosting.")
    
    # Check if credentials already exist
    aws_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
    
    if aws_key and aws_secret:
        print("✅ AWS credentials are already configured!")
        return True
    
    print("\n📋 You'll need the following:")
    print("  1. An AWS account (free tier is sufficient)")
    print("  2. AWS Access Key ID and Secret Access Key from an IAM user with proper permissions")
    
    proceed = input("\nWould you like to proceed with the setup? (y/n): ").lower()
    if proceed != 'y':
        print("\nSetup canceled. You can run this setup again later.")
        return False
    
    # Determine the .env file location
    dot_env_path = Path('.env')
    if not dot_env_path.exists():
        with open(dot_env_path, 'w') as f:
            f.write("# AWS credentials for share_df\n")
    
    # Ask if user wants guidance on creating an IAM user (best practice)
    iam_guidance = input("\nWould you like guidance on creating a proper IAM user instead of using root credentials? (y/n): ").lower()
    if iam_guidance == 'y':
        print("\n🔒 Setting up a Secure IAM User (Recommended) 🔒")
        print("\nFollow these steps to create a dedicated IAM user with limited permissions:")
        print("  1. Go to https://console.aws.amazon.com/iam/")
        print("  2. Click on 'Users' in the left menu, then 'Create user'")
        print("  3. Enter a username like 'share-df-app and create the user")
        print("  4. Select 'CreateAccess key', click Other - Programmatic access' and Create")
        print("  5. Click Add permission and create user group")
        print("  6. Search for and select these policies, and click add permissions:")
        print("     - AmazonS3FullAccess")
        print("     - AmazonCognitoDeveloperAuthenticatedIdentities (if using authentication)")
        print("     - CloudFrontFullAccess")
        print("  7. Click Next, review, and create the user")
        print("  8. IMPORTANT: Save the Access Key ID and Secret Access Key shown")
        print("     This is your ONLY chance to see the Secret Access Key!")
        
        print("\nAdvanced Security Notes:")
        print("  • Consider creating a custom policy with more restricted permissions")
        print("  • Set up MFA for the IAM user for additional security")
        print("  • Regularly rotate access keys using the AWS console\n")
        
        ready = input("Press Enter when you've created your IAM user and have the credentials ready...")
    
    print("\n🔑 AWS Credentials Setup 🔑")
    
    # Get AWS credentials
    print("\n🔐 Enter your AWS credentials below:")
    aws_key = input("AWS Access Key ID: ").strip()
    if not aws_key:
        print("❌ AWS Access Key ID is required. Setup canceled.")
        return False
    
    aws_secret = input("AWS Secret Access Key: ").strip()
    if not aws_secret:
        print("❌ AWS Secret Access Key is required. Setup canceled.")
        return False
    
    # Ask for optional settings
    print("\n🌎 Additional AWS settings (optional):")
    aws_region = input("AWS Region (press Enter for default 'us-east-1'): ").strip()
    aws_region = aws_region or "us-east-1"
    
    aws_bucket = input("S3 Bucket Name (press Enter for default 'sharedf-data'): ").strip()
    aws_bucket = aws_bucket or "sharedf-data"
    
    # Save to .env file
    try:
        print("\n💾 Saving credentials to .env file...")
        set_key(dot_env_path, "AWS_ACCESS_KEY_ID", aws_key)
        set_key(dot_env_path, "AWS_SECRET_ACCESS_KEY", aws_secret)
        set_key(dot_env_path, "AWS_REGION", aws_region)
        set_key(dot_env_path, "AWS_S3_BUCKET", aws_bucket)
        
        # Reload environment variables
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        print("✅ AWS credentials saved successfully!")
        
        print("\n🔧 Testing AWS configuration...")
        try:
            import boto3
            
            # Test if we can create AWS clients
            s3 = boto3.client(
                's3', 
                region_name=aws_region,
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret
            )
            
            print("✅ AWS connection successful!")
            
            # Check if bucket exists, create if not
            try:
                s3.head_bucket(Bucket=aws_bucket)
                print(f"✅ Bucket '{aws_bucket}' exists and is accessible")
            except:
                print(f"ℹ️  Bucket '{aws_bucket}' does not exist yet. It will be created when needed.")
                
            print("\n🎉 AWS setup complete! You're ready to use cloud hosting.")
            return True
            
        except Exception as e:
            print(f"❌ Error testing AWS configuration: {e}")
            print("Your credentials were saved, but there might be an issue with them.")
            print("You can try again or proceed with caution.")
            return True
            
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return False

def pandaBear(df: Union[pd.DataFrame, pl.DataFrame], 
             use_iframe: bool = False, 
             collaborative: bool = True, 
             share_with: Union[str, List[str]] = None, 
             log_level: str = "CRITICAL", 
             local: bool = False, 
             strict_dtype: bool = True,
             use_cloud: bool = False,
             df_name: str = None,
             df_description: str = "") -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Opens an interactive web editor for a pandas or polars DataFrame with authentication.
    
    Args:
        df (Union[pd.DataFrame, pl.DataFrame]): The DataFrame to edit.
        use_iframe (bool, optional): Whether to display the editor in an iframe (Google Colab only). Defaults to False.
        collaborative (bool, optional): Whether to enable real-time collaboration features. Defaults to True.
        share_with (Union[str, list], optional): Email(s) to share the editor with (requires collaborative=True). Defaults to None.
        log_level (str, optional): Logging level. Defaults to "CRITICAL".
        local (bool, optional): Whether to run in local mode without ngrok. Defaults to False.
        strict_dtype (bool, optional): Whether to enforce strict dtype checking. Defaults to True.
        use_cloud (bool, optional): Whether to use cloud-hosted mode with encryption. Defaults to False.
        df_name (str, optional): Name for the dataframe when using cloud mode. Defaults to None.
        df_description (str, optional): Description for the dataframe when using cloud mode. Defaults to "".
        
    Returns:
        Union[pd.DataFrame, pl.DataFrame]: The edited DataFrame in the same type as input.
    """
    if use_cloud:
        # Normalize share_with to a list
        if isinstance(share_with, str):
            share_with = [email.strip() for email in share_with.split(',') if email.strip()]
        
        # Check required AWS environment variables
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            print("\n⚠️  Cloud mode requires AWS credentials. Missing environment variables:")
            for var in missing_vars:
                print(f" - {var}")
            
            # Offer to set up the AWS credentials interactively
            setup_prompt = input("\nWould you like to set up AWS credentials now? (y/n): ")
            
            if setup_prompt.lower() == 'y':
                if _setup_aws_credentials():
                    # Check if credentials are now available
                    missing_vars = [var for var in required_vars if not os.environ.get(var)]
                    if not missing_vars:
                        print("\n✅ AWS credentials set up successfully. Continuing with cloud mode...")
                    else:
                        print("\n❌ Some credentials are still missing. Falling back to regular mode...")
                        from .server import start_editor
                        return start_editor(df, use_iframe=use_iframe, collaborative=collaborative, 
                                        share_with=share_with, log_level=log_level, local=local, 
                                        strict_dtype=strict_dtype)
                else:
                    print("\n❌ AWS setup was not completed. Falling back to regular mode...")
                    from .server import start_editor
                    return start_editor(df, use_iframe=use_iframe, collaborative=collaborative, 
                                    share_with=share_with, log_level=log_level, local=local, 
                                    strict_dtype=strict_dtype)
            else:
                # User doesn't want to set up AWS now
                print("\n📝 Example .env file content:")
                print("AWS_ACCESS_KEY_ID=your_access_key_here")
                print("AWS_SECRET_ACCESS_KEY=your_secret_key_here")
                print("AWS_REGION=us-east-1  # Optional, defaults to us-east-1")
                print("AWS_S3_BUCKET=your-bucket-name  # Optional, defaults to sharedf-data")
                
                # Fall back to regular mode
                print("\nFalling back to regular (non-cloud) mode...\n")
                from .server import start_editor
                return start_editor(df, use_iframe=use_iframe, collaborative=collaborative, 
                                share_with=share_with, log_level=log_level, local=local, 
                                strict_dtype=strict_dtype)
        
        # If we got here, AWS credentials are available
        # Use the cloud-based sharing
        from .cloud_server import cloud_share_dataframe
        
        # Auto-generate a name if none provided
        if not df_name:
            from datetime import datetime
            df_name = f"dataframe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"Using auto-generated name: {df_name}")
        
        print(f"\n☁️  Starting cloud-hosted DataFrame editor with {len(df)} rows and {len(df.columns)} columns...")
        
        # Share through the cloud
        return cloud_share_dataframe(
            df=df,
            share_with=share_with,
            name=df_name,
            description=df_description,
            log_level=log_level
        )
    else:
        # Use the original functionality
        from .server import start_editor
        return start_editor(df, use_iframe=use_iframe, collaborative=collaborative, 
                         share_with=share_with, log_level=log_level, local=local, 
                         strict_dtype=strict_dtype)

def retrieve_cloud_dataframe(session_id: str, 
                           df_id: str, 
                           encryption_key: str, 
                           version: str = None) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Retrieve a dataframe that was previously shared through cloud hosting.
    
    Args:
        session_id (str): The session ID of the shared dataframe
        df_id (str): The ID of the dataframe
        encryption_key (str): The encryption key for the dataframe
        version (str, optional): Specific version to retrieve, or None for latest
        
    Returns:
        Union[pd.DataFrame, pl.DataFrame]: The retrieved dataframe
    """
    from .cloud_server import retrieve_dataframe
    
    # Check for AWS credentials
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("\n⚠️  AWS credentials are required to retrieve cloud dataframes.")
        setup_prompt = input("\nWould you like to set up AWS credentials now? (y/n): ")
        
        if setup_prompt.lower() == 'y':
            if _setup_aws_credentials():
                # Credentials set up, continue
                pass
            else:
                raise ValueError("AWS credentials are required to retrieve cloud dataframes.")
        else:
            raise ValueError("AWS credentials are required to retrieve cloud dataframes.")
    
    print(f"Retrieving dataframe (ID: {df_id}, Session: {session_id})")
    if version:
        print(f"Requesting version: {version}")
    
    return retrieve_dataframe(session_id, df_id, encryption_key, version)

def list_cloud_versions(session_id: str, df_id: str) -> List[dict]:
    """
    List all versions of a cloud-hosted dataframe.
    
    Args:
        session_id (str): The session ID of the shared dataframe
        df_id (str): The ID of the dataframe
        
    Returns:
        List[dict]: List of version information
    """
    from .cloud_server import list_versions
    
    # Check for AWS credentials
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("\n⚠️  AWS credentials are required to list cloud dataframe versions.")
        setup_prompt = input("\nWould you like to set up AWS credentials now? (y/n): ")
        
        if setup_prompt.lower() == 'y':
            if _setup_aws_credentials():
                # Credentials set up, continue
                pass
            else:
                raise ValueError("AWS credentials are required to list cloud dataframe versions.")
        else:
            raise ValueError("AWS credentials are required to list cloud dataframe versions.")
    
    print(f"Listing versions for dataframe (ID: {df_id}, Session: {session_id})")
    versions = list_versions(session_id, df_id)
    
    # Print a nice table of versions
    if versions:
        print(f"\nFound {len(versions)} versions:")
        print("╔════════╦════════════════════════════╦═══════════════════════════════════╗")
        print("║ Version ║ Created At                ║ Description                       ║")
        print("╠════════╬════════════════════════════╬═══════════════════════════════════╣")
        
        for v in versions:
            version = v.get('version', 'Unknown')
            created = v.get('created_at', 'Unknown').replace('T', ' ').split('.')[0]
            desc = v.get('description', 'No description')
            if len(desc) > 35:
                desc = desc[:32] + "..."
            print(f"║ {version:^8} ║ {created:^26} ║ {desc:^35} ║")
            
        print("╚════════╩════════════════════════════╩═══════════════════════════════════╝")
    else:
        print("No versions found.")
    
    return versions

@pd.api.extensions.register_dataframe_accessor("pandaBear")
class PandaBearAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj
        
    def __call__(self, use_iframe: bool = False, 
                collaborative: bool = False, 
                share_with: Union[str, List[str]] = None, 
                log_level: str = "CRITICAL", 
                local: bool = False, 
                strict_dtype: bool = True,
                use_cloud: bool = False,
                df_name: str = None,
                df_description: str = ""):
        self._obj.update(pandaBear(self._obj, use_iframe=use_iframe, 
                                 collaborative=collaborative, 
                                 share_with=share_with, 
                                 log_level=log_level, 
                                 local=local, 
                                 strict_dtype=strict_dtype,
                                 use_cloud=use_cloud,
                                 df_name=df_name,
                                 df_description=df_description))
        return None

def _register_polars_extension():
    if not hasattr(pl.DataFrame, "pandaBear"):
        class PolarsBearAccessor:
            def __init__(self, polars_obj):
                self._obj = polars_obj
                
            def __call__(self, use_iframe: bool = False, 
                        collaborative: bool = False, 
                        share_with: Union[str, List[str]] = None, 
                        log_level: str = "CRITICAL", 
                        local: bool = False, 
                        strict_dtype: bool = True,
                        use_cloud: bool = False,
                        df_name: str = None,
                        df_description: str = ""):
                modified_df = pandaBear(self._obj, 
                                      use_iframe=use_iframe, 
                                      collaborative=collaborative, 
                                      share_with=share_with, 
                                      log_level=log_level, 
                                      local=local, 
                                      strict_dtype=strict_dtype,
                                      use_cloud=use_cloud,
                                      df_name=df_name,
                                      df_description=df_description)
                self._obj.clear()
                for col in modified_df.columns:
                    self._obj.with_columns(modified_df[col])
                return None
        
        setattr(pl.DataFrame, "pandaBear", property(lambda self: PolarsBearAccessor(self)))

_register_polars_extension()