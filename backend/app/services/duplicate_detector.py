import logging
import os
from typing import List, Dict, Set, Tuple
from collections import defaultdict
from PIL import Image
import imagehash
import io
from app.config import settings
from app.services.drive_service import DriveService


logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detects exact and near-duplicate files using MD5 and perceptual hashing"""
    
    def __init__(self, drive_service: DriveService):
        self.drive_service = drive_service
        self.phash_threshold = settings.PHASH_THRESHOLD
    
    def find_exact_duplicates(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group files by MD5 hash.
        Returns dict: {md5_hash: [file1, file2, ...]}
        Only returns groups with 2+ files (actual duplicates).
        """
        hash_groups = defaultdict(list)
        
        for file in files:
            # Skip folders and files without MD5
            if file['mimeType'] == 'application/vnd.google-apps.folder':
                continue
            
            md5 = file.get('md5Checksum')
            if not md5:
                logger.debug(f"File {file['name']} has no MD5 hash, skipping")
                continue
            
            hash_groups[md5].append(file)
        
        # Keep only groups with 2+ files
        duplicates = {k: v for k, v in hash_groups.items() if len(v) > 1}
        
        logger.info(f"Found {len(duplicates)} exact duplicate groups ({sum(len(v) for v in duplicates.values())} total duplicate files)")
        return duplicates
    
    def find_near_duplicates_phash(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Detect near-duplicates using perceptual hashing (pHash) of thumbnails.
        Only processes images, filters by MIME type.
        Returns dict: {phash: [file1, file2, ...]} for duplicates.
        """
        image_files = [
            f for f in files 
            if f['mimeType'].startswith('image/') and f.get('size', 0) > 0
        ]
        
        if not image_files:
            logger.info("No image files found for near-duplicate detection")
            return {}
        
        logger.info(f"Computing pHash for {len(image_files)} image files")
        
        phash_map = {}  # file_id -> phash
        
        # Download thumbnails and compute pHash
        for idx, file in enumerate(image_files):
            try:
                thumb_bytes = self.drive_service.download_thumbnail(file['id'])
                if not thumb_bytes:
                    logger.debug(f"No thumbnail for {file['name']}")
                    continue
                
                # Compute pHash
                image = Image.open(io.BytesIO(thumb_bytes))
                phash = imagehash.phash(image, hash_size=8)
                phash_map[file['id']] = phash
                
                # Progress logging
                if (idx + 1) % 10 == 0:
                    logger.info(f"Processed {idx + 1}/{len(image_files)} images for pHash")
            
            except Exception as e:
                logger.debug(f"Failed to compute pHash for {file['name']}: {e}")
                continue
        
        # Find near-duplicates by comparing pHash distances
        near_dup_groups = self._cluster_by_phash(files, phash_map)
        
        logger.info(f"Found {len(near_dup_groups)} near-duplicate groups")
        return near_dup_groups
    
    def _cluster_by_phash(self, files: List[Dict], phash_map: Dict[str, imagehash.ImageHash]) -> Dict[str, List[Dict]]:
        """
        Cluster files by pHash similarity.
        Uses threshold-based grouping: if distance < threshold, they're similar.
        """
        file_by_id = {f['id']: f for f in files}
        clusters = {}
        processed = set()
        cluster_id = 0
        
        file_ids = list(phash_map.keys())
        
        for i, file_id in enumerate(file_ids):
            if file_id in processed:
                continue
            
            phash1 = phash_map[file_id]
            cluster = [file_by_id[file_id]]
            processed.add(file_id)
            
            # Find all similar files
            for j in range(i + 1, len(file_ids)):
                other_id = file_ids[j]
                if other_id in processed:
                    continue
                
                phash2 = phash_map[other_id]
                distance = phash1 - phash2  # Hamming distance
                
                if distance < self.phash_threshold:
                    cluster.append(file_by_id[other_id])
                    processed.add(other_id)
            
            # Only keep clusters with 2+ files
            if len(cluster) > 1:
                clusters[f"cluster_{cluster_id}"] = cluster
                cluster_id += 1
        
        return clusters
    
    def create_duplicate_groups(self, exact_dups: Dict, near_dups: Dict) -> Dict[str, Dict]:
        """
        Merge exact and near-duplicate groups into a unified format.
        Returns: {group_id: {files: [...], type: 'exact' | 'near'}}
        """
        groups = {}
        group_id = 0
        
        # Add exact duplicates
        for hash_val, files in exact_dups.items():
            groups[f"group_{group_id}"] = {
                'files': files,
                'type': 'exact',
                'hash_value': hash_val,
                'size': len(files)
            }
            group_id += 1
        
        # Add near-duplicates
        for hash_cluster, files in near_dups.items():
            groups[f"group_{group_id}"] = {
                'files': files,
                'type': 'near',
                'hash_value': hash_cluster,
                'size': len(files)
            }
            group_id += 1
        
        return groups


def humanize_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"