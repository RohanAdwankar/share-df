import time
import logging
import json
import os
from typing import Dict, List, Union, Optional, Any, Tuple
from pathlib import Path
import pandas as pd
import polars as pl
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import threading

from .cloud import AWSCloudService
from dotenv import load_dotenv

logger = logging.getLogger("share_df")

class CloudManager:
    """
    Manager class for cloud-based dataframe sharing.
    Handles AWS infrastructure, dataframe versioning, and authentication.
    """
    
    def __init__(self, 
                 df: Union[pd.DataFrame, pl.DataFrame], 
                 share_with: List[str] = None,
                 name: str = None, 
                 description: str = "",
                 log_level: str = "CRITICAL"):
        
        # Configure logging level
        log_level = log_level.upper()
        numeric_level = getattr(logging, log_level, logging.CRITICAL)
        logger.setLevel(numeric_level)
        
        # Add a handler if none exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        # Store the dataframe
        self.df = df
        
        # Use provided name or generate a default
        self.name = name or f"dataframe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.description = description
        self.share_with = share_with or []
        
        # Check AWS credentials
        load_dotenv()
        self._check_aws_credentials()
        
        # Initialize the cloud service
        self.cloud_service = AWSCloudService()
        
        # Initialize event for shutdown notification
        self.shutdown_event = threading.Event()
        
        # Track versions and IDs
        self.df_info = None
        self.df_id = None
        self.encryption_key = None
        
        # Track metrics
        self.metrics = {
            "start_time": time.time(),
            "versions": 1,
            "viewers": 0
        }
    
    def _check_aws_credentials(self):
        """Check if AWS credentials are available."""
        required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
        missing_vars = [var for var in required_vars if not os.environ.get(var)]
        
        if missing_vars:
            logger.error(f"Missing AWS credentials: {', '.join(missing_vars)}")
            raise ValueError(f"AWS credentials are required. Missing: {', '.join(missing_vars)}")
    
    def _setup_cloud_infrastructure(self):
        """Set up AWS cloud infrastructure."""
        logger.info("Setting up cloud infrastructure...")
        
        # Ensure the S3 bucket exists
        if not self.cloud_service.ensure_bucket_exists():
            logger.error("Failed to create or verify S3 bucket")
            raise RuntimeError("Failed to set up AWS S3 bucket")
        
        # Set up authentication if share_with is provided
        if self.share_with:
            logger.info(f"Setting up authentication for {len(self.share_with)} users")
            self.cloud_service.setup_auth(self.share_with)
        
        # Upload static assets to S3
        logger.info("Uploading static assets to S3...")
        self.cloud_service.upload_static_assets()
    
    def upload_dataframe(self):
        """Upload the dataframe to cloud storage."""
        logger.info(f"Uploading dataframe to cloud: {self.name}")
        
        # Set up infrastructure if needed
        self._setup_cloud_infrastructure()
        
        # Upload the dataframe
        self.df_info = self.cloud_service.upload_dataframe(
            df=self.df,
            name=self.name,
            description=self.description
        )
        
        self.df_id = self.df_info.get("id")
        self.encryption_key = self.df_info.get("encryption_key")
        
        logger.info(f"Dataframe uploaded with ID: {self.df_id}")
        return self.df_info
    
    def update_dataframe_version(self, df: Union[pd.DataFrame, pl.DataFrame], version_description: str = None):
        """
        Update the dataframe with a new version.
        
        Args:
            df: Updated dataframe
            version_description: Description of the changes
        """
        if not self.df_id or not self.encryption_key:
            logger.error("Cannot update dataframe: No previous version found")
            raise ValueError("No previous version to update. Please upload the dataframe first.")
        
        # Generate version description if not provided
        if not version_description:
            version_description = f"Updated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Update the dataframe
        update_info = self.cloud_service.update_dataframe(
            df=df,
            df_id=self.df_id,
            encryption_key_b64=self.encryption_key,
            version_description=version_description
        )
        
        # Update our copy
        self.df = df
        self.metrics["versions"] += 1
        
        logger.info(f"Dataframe updated to version: {update_info.get('version')}")
        return update_info
    
    def get_share_url(self):
        """Get the shareable URL for the dataframe."""
        if not self.df_info or not self.df_info.get("share_url"):
            raise ValueError("Dataframe has not been uploaded yet")
            
        return self.df_info.get("share_url")
    
    def get_usage_metrics(self):
        """Get usage metrics for the cloud service."""
        cloud_metrics = self.cloud_service.get_usage_metrics()
        
        # Add our metrics
        cloud_metrics.update({
            "versions": self.metrics.get("versions", 1),
            "viewers": self.metrics.get("viewers", 0)
        })
        
        # Calculate total duration
        duration = time.time() - self.metrics["start_time"]
        cloud_metrics["duration"] = {
            "seconds": round(duration, 1),
            "minutes": round(duration / 60, 1),
            "formatted": f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m {int(duration % 60)}s"
        }
        
        return cloud_metrics
    
    def shutdown(self):
        """Signal shutdown."""
        self.shutdown_event.set()


def cloud_share_dataframe(df: Union[pd.DataFrame, pl.DataFrame], 
                         share_with: List[str] = None,
                         name: str = None,
                         description: str = "",
                         log_level: str = "CRITICAL") -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Share a dataframe through AWS cloud infrastructure.
    
    Args:
        df: DataFrame to share
        share_with: List of email addresses to share with
        name: Name for the dataframe
        description: Description of the dataframe
        log_level: Logging level
        
    Returns:
        The original dataframe (for method chaining)
    """
    try:
        # Initialize cloud manager
        cloud_manager = CloudManager(
            df=df,
            share_with=share_with,
            name=name,
            description=description,
            log_level=log_level
        )
        
        # Upload the dataframe
        df_info = cloud_manager.upload_dataframe()
        
        # Get and display the share URL
        share_url = cloud_manager.get_share_url()
        print(f"\n🔒 Encrypted share link: {share_url}")
        
        # Show details about the sharing
        print(f"\nDataframe '{df_info.get('name')}' uploaded to cloud")
        print(f"- Version: {df_info.get('latest_version')}")
        print(f"- Session ID: {df_info.get('session_id')}")
        
        # If authentication is set up, show info about it
        if share_with:
            print(f"\nShared with {len(share_with)} email(s):")
            for email in share_with:
                print(f"  - {email}")
        
        # Display metrics and estimated cost
        metrics = cloud_manager.get_usage_metrics()
        print(f"\nUsage metrics:")
        print(f"- Uploaded: {metrics.get('data_uploaded_mb')} MB")
        print(f"- Estimated cost: ${metrics.get('estimated_cost_usd')}")
        print(f"- API calls: {metrics.get('api_calls')}")
        
        print("\nNote: Your data is encrypted before being sent to the cloud.")
        print("      Only people with the link can access the data.")
        
        # Ask if user wants to wait for updates
        user_input = input("\nWould you like to wait for dataframe updates? (y/n): ")
        
        if user_input.lower() in ['y', 'yes']:
            print("\nWaiting for updates. Press Ctrl+C to retrieve the current dataframe...")
            try:
                # Wait until interrupted or shutdown event is set
                cloud_manager.shutdown_event.wait()
            except KeyboardInterrupt:
                print("\nInterrupted. Retrieving the final dataframe...")
        
        # Get the latest version of the dataframe
        try:
            updated_df = cloud_manager.cloud_service.get_dataframe(
                df_id=cloud_manager.df_id,
                encryption_key_b64=cloud_manager.encryption_key
            )
            
            final_metrics = cloud_manager.get_usage_metrics()
            print(f"\nFinal metrics:")
            print(f"- Versions created: {final_metrics.get('versions')}")
            print(f"- Total data transferred: {final_metrics.get('data_uploaded_mb') + final_metrics.get('data_downloaded_mb')} MB")
            print(f"- Total cost estimate: ${final_metrics.get('estimated_cost_usd')}")
            
            return updated_df
        except Exception as e:
            logger.error(f"Failed to retrieve updated dataframe: {e}")
            # Return original dataframe if retrieval fails
            return df
            
    except Exception as e:
        logger.error(f"Error in cloud_share_dataframe: {e}")
        print(f"\nError sharing dataframe: {e}")
        print("Falling back to original dataframe")
        return df


def retrieve_dataframe(session_id: str, df_id: str, encryption_key: str, version: str = None) -> Union[pd.DataFrame, pl.DataFrame]:
    """
    Retrieve a shared dataframe from the cloud.
    
    Args:
        session_id: Session ID for the dataframe
        df_id: Dataframe ID
        encryption_key: Encryption key (base64-encoded)
        version: Version to retrieve (or None for latest)
        
    Returns:
        Retrieved DataFrame
    """
    try:
        # Initialize cloud service
        cloud_service = AWSCloudService()
        
        # Override the session ID to match the shared one
        cloud_service.session_id = session_id
        
        # Retrieve the dataframe
        df = cloud_service.get_dataframe(
            df_id=df_id,
            encryption_key_b64=encryption_key,
            version=version
        )
        
        return df
            
    except Exception as e:
        logger.error(f"Error retrieving dataframe: {e}")
        raise ValueError(f"Failed to retrieve dataframe: {e}")


def list_versions(session_id: str, df_id: str) -> List[Dict[str, Any]]:
    """
    List all versions of a dataframe.
    
    Args:
        session_id: Session ID for the dataframe
        df_id: Dataframe ID
        
    Returns:
        List of version information
    """
    try:
        # Initialize cloud service
        cloud_service = AWSCloudService()
        
        # Override the session ID to match the shared one
        cloud_service.session_id = session_id
        
        # List versions
        versions = cloud_service.list_dataframe_versions(df_id)
        
        return versions
            
    except Exception as e:
        logger.error(f"Error listing versions: {e}")
        return []
