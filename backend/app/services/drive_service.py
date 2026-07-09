import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from typing import Optional, List, Dict
from app.config import settings

logger = logging.getLogger(__name__)


class DriveService:
    """Wrapper for Google Drive API with OAuth"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    def __init__(self, credentials: Optional[Credentials] = None):
        self.credentials = credentials
        self.service = None
        if credentials:
            self._init_service()
    
    def _init_service(self):
        """Initialize Drive API service"""
        if self.credentials:
            self.service = build('drive', 'v3', credentials=self.credentials)
    
    @staticmethod
    def get_auth_flow():
        """Create OAuth flow for PKCE (Electron app)"""
        flow = Flow.from_client_secrets_file(
            'credentials.json',  # Download from Google Cloud Console
            scopes=DriveService.SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        return flow
    
    @staticmethod
    def get_auth_url():
        """Generate authorization URL for user"""
        flow = DriveService.get_auth_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return auth_url, state, flow
    
    @staticmethod
    def exchange_code_for_token(code: str, flow: Flow) -> Credentials:
        """Exchange authorization code for access token"""
        try:
            flow.fetch_token(code=code)
            credentials = flow.credentials
            return credentials
        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            raise
    
    def refresh_credentials(self) -> bool:
        """Refresh access token using refresh token"""
        try:
            if self.credentials and self.credentials.refresh_token:
                request = Request()
                self.credentials.refresh(request)
                self._init_service()
                return True
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            return False
        return False
    
    def list_all_files(self, folder_id: str = "root") -> List[Dict]:
        """
        List all files in a folder (recursive).
        Returns list of files with: id, name, size, mimeType, md5Checksum, createdTime, modifiedTime, webViewLink
        """
        all_files = []
        page_token = None
        
        try:
            while True:
                # Query for both files and folders
                results = self.service.files().list(
                    q=f"'{folder_id}' in parents and trashed=false",
                    spaces='drive',
                    fields='files(id, name, size, mimeType, md5Checksum, createdTime, modifiedTime, webViewLink, owners)',
                    pageSize=1000,
                    pageToken=page_token
                ).execute()
                
                files = results.get('files', [])
                all_files.extend(files)
                
                # Recursively get files from subfolders
                for file in files:
                    if file['mimeType'] == 'application/vnd.google-apps.folder':
                        try:
                            subfolder_files = self.list_all_files(file['id'])
                            all_files.extend(subfolder_files)
                        except Exception as e:
                            logger.warning(f"Failed to list files in folder {file['id']}: {e}")
                
                page_token = results.get('nextPageToken', None)
                if not page_token:
                    break
            
            logger.info(f"Listed {len(all_files)} files from Drive")
            return all_files
        
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            raise
    
    def download_file(self, file_id: str, local_path: str) -> bool:
        """Download file from Drive"""
        try:
            request = self.service.files().get_media(fileId=file_id)
            with open(local_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            logger.info(f"Downloaded file {file_id} to {local_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return False
    
    def download_thumbnail(self, file_id: str) -> Optional[bytes]:
        """
        Download thumbnail for image file.
        Returns bytes if successful, None otherwise.
        """
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request, chunksize=-1)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            file_content.seek(0)
            logger.debug(f"Downloaded thumbnail for {file_id}")
            return file_content.read()
        except Exception as e:
            logger.debug(f"Failed to download thumbnail for {file_id}: {e}")
            return None
    
    def move_file(self, file_id: str, new_folder_id: str) -> bool:
        """Move file to a different folder"""
        try:
            # Get current parents
            file = self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
            
            previous_parents = ",".join(file.get('parents', []))
            
            # Move to new folder
            self.service.files().update(
                fileId=file_id,
                addParents=new_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            
            logger.info(f"Moved file {file_id} to folder {new_folder_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to move file {file_id}: {e}")
            return False
    
    def create_folder(self, folder_name: str, parent_id: str = "root") -> Optional[str]:
        """Create a new folder and return its ID"""
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder {folder_name} with ID {folder_id}")
            return folder_id
        except Exception as e:
            logger.error(f"Failed to create folder {folder_name}: {e}")
            return None
    
    def get_or_create_folder(self, folder_name: str, parent_id: str = "root") -> Optional[str]:
        """Get folder ID if exists, otherwise create it"""
        try:
            # Check if folder already exists
            results = self.service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false",
                spaces='drive',
                fields='files(id)',
                pageSize=1
            ).execute()
            
            files = results.get('files', [])
            if files:
                folder_id = files[0]['id']
                logger.info(f"Found existing folder {folder_name} with ID {folder_id}")
                return folder_id
            
            # Create new folder
            return self.create_folder(folder_name, parent_id)
        except Exception as e:
            logger.error(f"Failed to get or create folder {folder_name}: {e}")
            return None