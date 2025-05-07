import os
import boto3
import json
import uuid
import time
import base64
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import polars as pl
from cryptography.fernet import Fernet
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from dotenv import load_dotenv

logger = logging.getLogger("share_df")

class AWSCloudService:
    """
    Service for handling AWS infrastructure for dataframe sharing.
    Provides transparent encryption and versioning.
    """
    
    def __init__(self, region: str = None, bucket_name: str = None):
        load_dotenv()
        self.aws_region = region or os.environ.get('AWS_REGION', 'us-east-1')
        self.bucket_name = bucket_name or os.environ.get('AWS_S3_BUCKET', 'sharedf-data')
        self.cloudfront_domain = os.environ.get('AWS_CLOUDFRONT_DOMAIN', '')
        self.cognito_user_pool_id = os.environ.get('AWS_COGNITO_USER_POOL_ID', '')
        self.cognito_client_id = os.environ.get('AWS_COGNITO_CLIENT_ID', '')
        
        # Initialize AWS clients
        self.s3 = self._create_s3_client()
        self.cloudfront = self._create_cloudfront_client()
        self.cognito = self._create_cognito_client()
        self.cloudwatch = self._create_cloudwatch_client()
        
        # Generate a unique session ID for this share instance
        self.session_id = str(uuid.uuid4())
        
        # Initialize usage metrics tracking
        self.metrics = {
            'data_bytes_uploaded': 0,
            'data_bytes_downloaded': 0,
            'api_calls': 0,
            'start_time': time.time()
        }
    
    def _create_s3_client(self):
        """Create an S3 client with proper credentials."""
        try:
            return boto3.client(
                's3', 
                region_name=self.aws_region,
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            logger.error(f"Failed to create S3 client: {e}")
            return None
    
    def _create_cloudfront_client(self):
        """Create a CloudFront client with proper credentials."""
        try:
            return boto3.client(
                'cloudfront', 
                region_name=self.aws_region,
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            logger.error(f"Failed to create CloudFront client: {e}")
            return None
    
    def _create_cognito_client(self):
        """Create a Cognito client with proper credentials."""
        try:
            return boto3.client(
                'cognito-idp', 
                region_name=self.aws_region,
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            logger.error(f"Failed to create Cognito client: {e}")
            return None
    
    def _create_cloudwatch_client(self):
        """Create a CloudWatch client for usage metrics."""
        try:
            return boto3.client(
                'cloudwatch', 
                region_name=self.aws_region,
                aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
            )
        except Exception as e:
            logger.error(f"Failed to create CloudWatch client: {e}")
            return None
    
    def ensure_bucket_exists(self) -> bool:
        """Ensure the S3 bucket exists, create it if it doesn't."""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Bucket {self.bucket_name} exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"Bucket {self.bucket_name} does not exist, creating...")
                try:
                    if self.aws_region == 'us-east-1':
                        self.s3.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.aws_region}
                        )
                    
                    # Enable versioning on the bucket
                    self.s3.put_bucket_versioning(
                        Bucket=self.bucket_name,
                        VersioningConfiguration={'Status': 'Enabled'}
                    )
                    
                    logger.info(f"Created bucket {self.bucket_name} with versioning enabled")
                    return True
                except Exception as e:
                    logger.error(f"Failed to create bucket: {e}")
                    return False
            else:
                logger.error(f"Error checking bucket: {e}")
                return False
                
    def setup_auth(self, share_with: List[str] = None) -> bool:
        """
        Set up authentication with Cognito if needed.
        
        Args:
            share_with: List of email addresses to share with
            
        Returns:
            bool: True if authentication setup was successful
        """
        # Check if auth is already set up
        if self.cognito_user_pool_id and self.cognito_client_id:
            return True
            
        # Create a new user pool if needed
        try:
            # Create a user pool
            user_pool_name = f"share-df-{self.session_id[:8]}"
            response = self.cognito.create_user_pool(
                PoolName=user_pool_name,
                AutoVerifiedAttributes=['email'],
                UsernameAttributes=['email'],
                AdminCreateUserConfig={
                    'AllowAdminCreateUserOnly': True
                }
            )
            
            self.cognito_user_pool_id = response['UserPool']['Id']
            
            # Create a client for the user pool
            client_response = self.cognito.create_user_pool_client(
                UserPoolId=self.cognito_user_pool_id,
                ClientName=f"share-df-client-{self.session_id[:8]}",
                GenerateSecret=False,
                ExplicitAuthFlows=['ALLOW_USER_PASSWORD_AUTH', 'ALLOW_ADMIN_USER_PASSWORD_AUTH'],
                AllowedOAuthFlows=['code'],
                AllowedOAuthScopes=['phone', 'email', 'openid', 'profile'],
                CallbackURLs=[f'https://{self.cloudfront_domain}/auth/callback'],
                LogoutURLs=[f'https://{self.cloudfront_domain}/auth/logout']
            )
            
            self.cognito_client_id = client_response['UserPoolClient']['ClientId']
            
            # Create domain for hosted UI
            domain_prefix = f"share-df-{self.session_id[:8]}"
            self.cognito.create_user_pool_domain(
                Domain=domain_prefix,
                UserPoolId=self.cognito_user_pool_id
            )
            
            # Add the specified users if provided
            if share_with:
                for email in share_with:
                    try:
                        self.cognito.admin_create_user(
                            UserPoolId=self.cognito_user_pool_id,
                            Username=email,
                            UserAttributes=[
                                {'Name': 'email', 'Value': email},
                                {'Name': 'email_verified', 'Value': 'true'}
                            ],
                            DesiredDeliveryMediums=['EMAIL']
                        )
                        logger.info(f"Added user {email} to Cognito user pool")
                    except ClientError as e:
                        logger.error(f"Failed to add user {email}: {e}")
            
            logger.info(f"Created Cognito user pool {self.cognito_user_pool_id} and client {self.cognito_client_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to set up authentication: {e}")
            return False
    
    def generate_encryption_key(self) -> bytes:
        """Generate a new encryption key."""
        return Fernet.generate_key()
    
    def encrypt_data(self, data: Dict[str, Any], encryption_key: bytes) -> bytes:
        """Encrypt data with the given key."""
        fernet = Fernet(encryption_key)
        serialized_data = json.dumps(data).encode('utf-8')
        return fernet.encrypt(serialized_data)
    
    def decrypt_data(self, encrypted_data: bytes, encryption_key: bytes) -> Dict[str, Any]:
        """Decrypt data with the given key."""
        fernet = Fernet(encryption_key)
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data)
    
    def upload_static_assets(self):
        """Upload static frontend assets to S3."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_dir = os.path.join(base_dir, "share_df", "static")
        
        if not os.path.exists(static_dir):
            logger.error(f"Static directory not found: {static_dir}")
            return False
        
        # Upload all static assets with appropriate content types
        for root, dirs, files in os.walk(static_dir):
            for file in files:
                local_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_path, start=static_dir)
                s3_key = f"static/{rel_path}"
                
                # Determine content type based on file extension
                content_type = self._get_content_type(file)
                
                try:
                    with open(local_path, 'rb') as f:
                        content = f.read()
                        self.metrics['data_bytes_uploaded'] += len(content)
                        
                        self.s3.put_object(
                            Bucket=self.bucket_name,
                            Key=s3_key,
                            Body=content,
                            ContentType=content_type
                        )
                    logger.debug(f"Uploaded static asset: {s3_key}")
                except Exception as e:
                    logger.error(f"Failed to upload static asset {s3_key}: {e}")
        
        logger.info(f"Uploaded static assets to S3 bucket {self.bucket_name}")
        return True
    
    def _get_content_type(self, filename: str) -> str:
        """Determine content type based on file extension."""
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml'
        }
        return content_types.get(ext, 'application/octet-stream')
    
    def upload_dataframe(self, 
                         df: Union[pd.DataFrame, pl.DataFrame], 
                         name: str = "default", 
                         description: str = "") -> Dict[str, str]:
        """
        Upload a dataframe to S3 with encryption.
        
        Args:
            df: DataFrame to upload
            name: Name to identify this dataframe
            description: Optional description
            
        Returns:
            Dict with dataframe info including access URL
        """
        # Ensure the bucket exists
        if not self.ensure_bucket_exists():
            raise RuntimeError("Failed to ensure S3 bucket exists")
            
        # Generate dataframe ID if not provided
        df_id = hashlib.md5(f"{name}_{self.session_id}".encode()).hexdigest()[:12]
        
        # Convert to pandas if needed
        if isinstance(df, pl.DataFrame):
            df_data = df.to_pandas()
            original_type = "polars"
        else:
            df_data = df
            original_type = "pandas"
            
        # Convert DataFrame to records for JSON serialization
        serialized_data = {
            "data": df_data.to_dict(orient='records'),
            "columns": list(df_data.columns),
            "dtypes": {col: str(df_data[col].dtype) for col in df_data.columns},
            "original_type": original_type,
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "version_description": "Initial version"
        }
        
        # Measure data size for metrics
        data_json = json.dumps(serialized_data)
        data_size = len(data_json.encode('utf-8'))
        self.metrics['data_bytes_uploaded'] += data_size
        self.metrics['api_calls'] += 1
        
        # Generate encryption key
        encryption_key = self.generate_encryption_key()
        
        # Encrypt the data
        encrypted_data = self.encrypt_data(serialized_data, encryption_key)
        
        # Calculate upload path
        data_key = f"dataframes/{self.session_id}/{df_id}/v1.0/data.enc"
        
        # Upload to S3
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=data_key,
                Body=encrypted_data,
                Metadata={
                    'name': name,
                    'description': description,
                    'version': '1.0',
                    'encrypted': 'true'
                }
            )
            
            # Save metadata separately (unencrypted but without actual data)
            metadata = {
                "id": df_id,
                "session_id": self.session_id,
                "name": name,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "latest_version": "1.0",
                "versions": [{
                    "version": "1.0",
                    "description": "Initial version",
                    "created_at": datetime.now().isoformat(),
                    "size_bytes": data_size
                }]
            }
            
            metadata_key = f"dataframes/{self.session_id}/{df_id}/metadata.json"
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata),
                ContentType='application/json'
            )
            
            # Generate pre-signed URLs
            data_url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': data_key},
                ExpiresIn=604800  # 7 days in seconds
            )
            
            metadata_url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': metadata_key},
                ExpiresIn=604800  # 7 days in seconds
            )
            
            # Convert binary key to base64 string for easy transmission
            encryption_key_b64 = base64.b64encode(encryption_key).decode('utf-8')
            
            # Update metrics
            self._record_usage_metrics()
            
            return {
                "id": df_id,
                "session_id": self.session_id,
                "name": name,
                "encryption_key": encryption_key_b64,
                "data_url": data_url,
                "metadata_url": metadata_url,
                "share_url": self._generate_share_url(df_id, encryption_key_b64),
                "latest_version": "1.0"
            }
            
        except Exception as e:
            logger.error(f"Failed to upload dataframe to S3: {e}")
            raise
    
    def update_dataframe(self, 
                         df: Union[pd.DataFrame, pl.DataFrame], 
                         df_id: str,
                         encryption_key_b64: str,
                         version_description: str = "Updated version") -> Dict[str, str]:
        """
        Save a new version of an existing dataframe.
        
        Args:
            df: Updated DataFrame
            df_id: ID of the dataframe to update
            encryption_key_b64: Base64 encoded encryption key
            version_description: Description of this version
            
        Returns:
            Dict with update info
        """
        try:
            # Retrieve current metadata
            metadata_key = f"dataframes/{self.session_id}/{df_id}/metadata.json"
            response = self.s3.get_object(Bucket=self.bucket_name, Key=metadata_key)
            metadata = json.loads(response['Body'].read().decode('utf-8'))
            
            # Calculate new version number
            latest_version = metadata["latest_version"]
            major, minor = map(int, latest_version.split('.'))
            new_version = f"{major}.{minor + 1}"
            
            # Convert to pandas if needed
            if isinstance(df, pl.DataFrame):
                df_data = df.to_pandas()
                original_type = "polars"
            else:
                df_data = df
                original_type = "pandas"
            
            # Prepare serialized data
            serialized_data = {
                "data": df_data.to_dict(orient='records'),
                "columns": list(df_data.columns),
                "dtypes": {col: str(df_data[col].dtype) for col in df_data.columns},
                "original_type": original_type,
                "name": metadata["name"],
                "description": metadata["description"],
                "updated_at": datetime.now().isoformat(),
                "version": new_version,
                "version_description": version_description
            }
            
            # Measure data size for metrics
            data_json = json.dumps(serialized_data)
            data_size = len(data_json.encode('utf-8'))
            self.metrics['data_bytes_uploaded'] += data_size
            self.metrics['api_calls'] += 1
            
            # Decrypt the encryption key
            encryption_key = base64.b64decode(encryption_key_b64)
            
            # Encrypt the updated data
            encrypted_data = self.encrypt_data(serialized_data, encryption_key)
            
            # Save the new version
            data_key = f"dataframes/{self.session_id}/{df_id}/v{new_version}/data.enc"
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=data_key,
                Body=encrypted_data,
                Metadata={
                    'name': metadata["name"],
                    'description': metadata["description"],
                    'version': new_version,
                    'encrypted': 'true'
                }
            )
            
            # Update metadata
            metadata["latest_version"] = new_version
            metadata["versions"].append({
                "version": new_version,
                "description": version_description,
                "created_at": datetime.now().isoformat(),
                "size_bytes": data_size
            })
            
            # Save updated metadata
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata),
                ContentType='application/json'
            )
            
            # Generate presigned URL for the new version
            data_url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': data_key},
                ExpiresIn=604800  # 7 days
            )
            
            # Update metrics
            self._record_usage_metrics()
            
            return {
                "id": df_id,
                "session_id": self.session_id,
                "version": new_version,
                "data_url": data_url,
                "share_url": self._generate_share_url(df_id, encryption_key_b64, version=new_version)
            }
        
        except Exception as e:
            logger.error(f"Failed to update dataframe: {e}")
            raise
    
    def get_dataframe(self, 
                     df_id: str, 
                     encryption_key_b64: str, 
                     version: str = None) -> Union[pd.DataFrame, pl.DataFrame]:
        """
        Retrieve a dataframe from S3.
        
        Args:
            df_id: ID of the dataframe to retrieve
            encryption_key_b64: Base64 encoded encryption key
            version: Specific version to retrieve, or None for latest
            
        Returns:
            DataFrame in its original format (pandas or polars)
        """
        try:
            # Get metadata to find latest version if version not specified
            metadata_key = f"dataframes/{self.session_id}/{df_id}/metadata.json"
            metadata_response = self.s3.get_object(Bucket=self.bucket_name, Key=metadata_key)
            metadata = json.loads(metadata_response['Body'].read().decode('utf-8'))
            
            self.metrics['data_bytes_downloaded'] += len(json.dumps(metadata).encode('utf-8'))
            
            # Use specified version or latest
            version_to_fetch = version or metadata["latest_version"]
            
            # Get the encrypted data
            data_key = f"dataframes/{self.session_id}/{df_id}/v{version_to_fetch}/data.enc"
            response = self.s3.get_object(Bucket=self.bucket_name, Key=data_key)
            encrypted_data = response['Body'].read()
            
            self.metrics['data_bytes_downloaded'] += len(encrypted_data)
            self.metrics['api_calls'] += 1
            
            # Decrypt the data
            encryption_key = base64.b64decode(encryption_key_b64)
            decrypted_data = self.decrypt_data(encrypted_data, encryption_key)
            
            # Convert to DataFrame
            df = pd.DataFrame(decrypted_data["data"])
            
            # Convert back to original type if necessary
            if decrypted_data["original_type"] == "polars":
                df = pl.from_pandas(df)
            
            # Update metrics
            self._record_usage_metrics()
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to retrieve dataframe: {e}")
            raise
    
    def list_dataframe_versions(self, df_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of available versions for a dataframe.
        
        Args:
            df_id: ID of the dataframe
            
        Returns:
            List of version information
        """
        try:
            # Get metadata
            metadata_key = f"dataframes/{self.session_id}/{df_id}/metadata.json"
            response = self.s3.get_object(Bucket=self.bucket_name, Key=metadata_key)
            metadata = json.loads(response['Body'].read().decode('utf-8'))
            
            self.metrics['api_calls'] += 1
            self.metrics['data_bytes_downloaded'] += len(response['Body'].read())
            
            return metadata["versions"]
            
        except Exception as e:
            logger.error(f"Failed to list dataframe versions: {e}")
            return []
    
    def list_dataframes(self) -> List[Dict[str, Any]]:
        """
        List all dataframes in the current session.
        
        Returns:
            List of dataframe metadata
        """
        try:
            prefix = f"dataframes/{self.session_id}/"
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix, Delimiter='/')
            
            self.metrics['api_calls'] += 1
            
            dataframes = []
            
            # Process common prefixes (one for each dataframe)
            for prefix_obj in response.get('CommonPrefixes', []):
                df_prefix = prefix_obj.get('Prefix', '')
                df_id = df_prefix.split('/')[-2]
                
                # Get metadata for this dataframe
                try:
                    metadata_key = f"{df_prefix}metadata.json"
                    metadata_response = self.s3.get_object(Bucket=self.bucket_name, Key=metadata_key)
                    metadata = json.loads(metadata_response['Body'].read().decode('utf-8'))
                    dataframes.append(metadata)
                    
                    self.metrics['data_bytes_downloaded'] += len(metadata_response['Body'].read())
                except Exception as e:
                    logger.error(f"Error retrieving metadata for {df_id}: {e}")
            
            return dataframes
            
        except Exception as e:
            logger.error(f"Failed to list dataframes: {e}")
            return []
    
    def delete_dataframe(self, df_id: str) -> bool:
        """
        Delete a dataframe and all its versions.
        
        Args:
            df_id: ID of the dataframe to delete
            
        Returns:
            True if successful
        """
        try:
            # List all objects with the dataframe prefix
            prefix = f"dataframes/{self.session_id}/{df_id}/"
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            
            self.metrics['api_calls'] += 1
            
            # Delete all objects
            if 'Contents' in response:
                objects = [{'Key': obj['Key']} for obj in response['Contents']]
                self.s3.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': objects}
                )
                
                logger.info(f"Deleted dataframe {df_id} with {len(objects)} objects")
                return True
            
            logger.warning(f"No objects found for dataframe {df_id}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete dataframe: {e}")
            return False
    
    def _generate_share_url(self, df_id: str, encryption_key_b64: str, version: str = None) -> str:
        """Generate a shareable URL for a dataframe."""
        if self.cloudfront_domain:
            base_url = f"https://{self.cloudfront_domain}"
        else:
            # Fall back to direct S3 URL if no CloudFront domain is set up
            base_url = f"https://{self.bucket_name}.s3.amazonaws.com"
        
        params = {
            "id": df_id,
            "sid": self.session_id,
            "key": encryption_key_b64
        }
        
        if version:
            params["v"] = version
            
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}/view?{query_string}"
    
    def get_usage_metrics(self) -> Dict[str, Any]:
        """
        Get current usage metrics.
        
        Returns:
            Dict with usage metrics
        """
        duration = time.time() - self.metrics['start_time']
        
        return {
            "data_uploaded_mb": round(self.metrics['data_bytes_uploaded'] / (1024 * 1024), 2),
            "data_downloaded_mb": round(self.metrics['data_bytes_downloaded'] / (1024 * 1024), 2),
            "api_calls": self.metrics['api_calls'],
            "duration_seconds": round(duration, 1),
            "estimated_cost_usd": self._estimate_cost()
        }
    
    def _estimate_cost(self) -> float:
        """
        Estimate AWS cost based on current usage.
        
        Returns:
            Estimated cost in USD
        """
        # S3 pricing (approximate)
        s3_storage_gb = (self.metrics['data_bytes_uploaded'] / (1024 * 1024 * 1024))
        s3_storage_cost = s3_storage_gb * 0.023  # $0.023 per GB-month
        
        # S3 request pricing
        s3_request_cost = self.metrics['api_calls'] * 0.0000004  # $0.0004 per 1000 requests
        
        # Data transfer pricing
        data_transfer_gb = (self.metrics['data_bytes_downloaded'] / (1024 * 1024 * 1024))
        data_transfer_cost = data_transfer_gb * 0.09  # $0.09 per GB
        
        # CloudFront costs (if used)
        cloudfront_cost = 0
        if self.cloudfront_domain:
            cloudfront_requests = self.metrics['api_calls'] * 0.5  # Assume 50% of requests go through CloudFront
            cloudfront_cost = (cloudfront_requests * 0.0000001)  # $0.0001 per 10,000 requests
            
        # Cognito costs (if used)
        cognito_cost = 0
        if self.cognito_user_pool_id:
            cognito_cost = 0.0055  # $0.0055 per MAU
            
        # Total cost
        total_cost = s3_storage_cost + s3_request_cost + data_transfer_cost + cloudfront_cost + cognito_cost
        
        return round(max(0.01, total_cost), 4)  # Minimum $0.01 to avoid showing $0.0000
    
    def _record_usage_metrics(self):
        """Record current usage metrics to CloudWatch."""
        try:
            if not self.cloudwatch:
                return
                
            # Update CloudWatch metrics
            self.cloudwatch.put_metric_data(
                Namespace='ShareDF',
                MetricData=[
                    {
                        'MetricName': 'DataUploaded',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': self.session_id}
                        ],
                        'Value': self.metrics['data_bytes_uploaded'],
                        'Unit': 'Bytes'
                    },
                    {
                        'MetricName': 'DataDownloaded',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': self.session_id}
                        ],
                        'Value': self.metrics['data_bytes_downloaded'],
                        'Unit': 'Bytes'
                    },
                    {
                        'MetricName': 'ApiCalls',
                        'Dimensions': [
                            {'Name': 'SessionId', 'Value': self.session_id}
                        ],
                        'Value': self.metrics['api_calls'],
                        'Unit': 'Count'
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to record metrics: {e}")

    def get_account_connection_status(self) -> Dict[str, Any]:
        """
        Check the status of AWS connections.
        
        Returns:
            Dict with connection status for each service
        """
        status = {
            "s3": {"connected": False, "message": "Not connected"},
            "cognito": {"connected": False, "message": "Not connected"},
            "cloudfront": {"connected": False, "message": "Not connected"},
            "cloudwatch": {"connected": False, "message": "Not connected"},
        }
        
        # Check S3 connection
        try:
            self.s3.list_buckets()
            status["s3"] = {"connected": True, "message": "Connected successfully"}
        except Exception as e:
            status["s3"] = {"connected": False, "message": str(e)}
        
        # Check Cognito connection
        if self.cognito:
            try:
                self.cognito.list_user_pools(MaxResults=1)
                status["cognito"] = {"connected": True, "message": "Connected successfully"}
            except Exception as e:
                status["cognito"] = {"connected": False, "message": str(e)}
        
        # Check CloudFront connection
        if self.cloudfront:
            try:
                self.cloudfront.list_distributions(MaxItems='1')
                status["cloudfront"] = {"connected": True, "message": "Connected successfully"}
            except Exception as e:
                status["cloudfront"] = {"connected": False, "message": str(e)}
        
        # Check CloudWatch connection
        if self.cloudwatch:
            try:
                self.cloudwatch.list_metrics(Namespace='AWS/S3', MetricName='BucketSizeBytes')
                status["cloudwatch"] = {"connected": True, "message": "Connected successfully"}
            except Exception as e:
                status["cloudwatch"] = {"connected": False, "message": str(e)}
        
        return status