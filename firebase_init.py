"""
Firebase Orchestration Core for Evolutionary Music System
Manages state, traceability, and inter-service communication
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import firebase_admin
from firebase_admin import credentials, firestore, storage
from firebase_admin.exceptions import FirebaseError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TrackExperiment:
    """DNA representation of a track experiment"""
    dna_id: str
    dna_vector: Dict[str, Any]
    generation: int
    parent_ids: Optional[list] = None
    mutation_rate: float = 0.2
    technical_score: Optional[float] = None
    perceptual_score: Optional[float] = None
    overall_score: Optional[float] = None
    audio_path: Optional[str] = None
    created_at: str = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()

class FirebaseOrchestrator:
    """Manages Firebase connections and data operations"""
    
    def __init__(self, service_account_path: str = None, storage_bucket: str = None):
        """
        Initialize Firebase connection
        
        Args:
            service_account_path: Path to service account JSON file
            storage_bucket: Firebase Storage bucket name
        """
        try:
            if not firebase_admin._apps:
                if service_account_path and os.path.exists(service_account_path):
                    cred = credentials.Certificate(service_account_path)
                else:
                    # Try environment variable
                    service_account_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
                    if service_account_json:
                        cred = credentials.Certificate(json.loads(service_account_json))
                    else:
                        raise ValueError("No Firebase credentials provided")
                
                firebase_admin.initialize_app(cred, {
                    'storageBucket': storage_bucket or os.getenv('FIREBASE_STORAGE_BUCKET')
                })
            
            self.db = firestore.client()
            self.bucket = storage.bucket() if storage_bucket else None
            self._ensure_collections()
            logger.info("Firebase Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    def _ensure_collections(self):
        """Ensure required collections exist with sample documents"""
        collections = [
            'track_experiments',
            'generation_cycles', 
            'distribution_queue',
            'performance_metrics'
        ]
        
        for collection in collections:
            try:
                # Try to create a test document to verify collection exists
                test_doc = self.db.collection(collection).document('_test')
                test_doc.set({'test': True, 'timestamp': firestore.SERVER_TIMESTAMP})
                test_doc.delete()
            except Exception as e:
                logger.warning(f"Collection {collection} may not exist: {str(e)}")
    
    def save_track_experiment(self, experiment: TrackExperiment) -> str:
        """
        Save track experiment to Firestore
        
        Args:
            experiment: TrackExperiment object
            
        Returns:
            Document ID of saved experiment
        """
        try:
            doc_ref = self.db.collection('track_experiments').document(experiment.dna_id)
            doc_ref.set(asdict(experiment))
            logger.info(f"Saved experiment {experiment.dna_id} to Firestore")
            return experiment.dna_id
        except Exception as e:
            logger.error(f"Failed to save experiment: {str(e)}")
            raise
    
    def get_best_experiments(self, limit: int = 10, min_score: float = 0.7) -> list:
        """
        Retrieve best performing experiments
        
        Args:
            limit: Maximum number of experiments to return
            min_score: Minimum overall score threshold
            
        Returns:
            List of TrackExperiment objects
        """
        try:
            query = (self.db.collection('track_experiments')
                     .where('overall_score', '>=', min_score)
                     .order_by('overall_score', direction=firestore.Query.DESCENDING)
                     .limit(limit))
            
            results = query.stream()
            experiments = []
            for doc in results:
                data = doc.to_dict()
                experiments.append(TrackExperiment(**data))
            
            logger.info(f"Retrieved {len(experiments)} best experiments")
            return experiments
            
        except Exception as e:
            logger.error(f"Failed to get best experiments: {str(e)}")
            return []
    
    def upload_audio_file(self, local_path: str, destination_path: str) -> str:
        """
        Upload audio file to Firebase Storage
        
        Args:
            local_path: Path to local audio file
            destination_path: Destination path in storage
            
        Returns:
            Public URL of uploaded file
        """
        if not self.bucket:
            raise ValueError("Storage bucket not configured")
        
        try:
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Audio file not found: {local_path}")
            
            blob = self.bucket.blob(destination_path)
            blob.upload_from_filename(local_path)
            
            # Make the blob publicly accessible
            blob.make_public()
            url = blob.public_url
            
            logger.info(f"Uploaded {local_path} to {destination_path}")
            return url
            
        except Exception as e:
            logger.error(f"Failed to upload audio file: {str(e)}")
            raise
    
    def log_distribution_state(self, track_id: str, state: str, metadata: Dict = None):
        """
        Log distribution state changes
        
        Args:
            track_id: ID of the track
            state: Current state (QUEUED, PROCESSING, UPLOADING, VERIFYING, PUBLISHED, FAILED)
            metadata: Additional metadata
        """
        try:
            valid_states = ['QUEUED', 'PROCESSING', 'UPLOADING', 'VERIFYING', 'PUBLISHED', 'FAILED']
            if state not in valid_states:
                raise ValueError(f"Invalid state. Must be one of: {valid_states}")
            
            doc_data = {
                'track_id': track_id,
                'state': state,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'metadata': metadata or {}
            }
            
            if state == 'FAILED' and metadata and 'error' in metadata:
                doc_data['error'] = metadata['error']
                doc_data['retry_count'] = metadata.get('retry_count', 0)
            
            self.db.collection('distribution_queue').document(track_id).set(doc_data)
            logger.info(f"Track {track_id} moved to state: {state}")
            
        except Exception as e:
            logger.error(f"Failed to log distribution state: {str(e)}")
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the evolution process
        
        Returns:
            Dictionary with generation statistics
        """
        try:
            stats = {
                'total_experiments': 0,
                'average_score': 0.0,
                'best_score': 0.0,
                'generation_counts': {}
            }
            
            # Get all experiments
            experiments = self.db.collection('track_experiments').stream()
            
            scores = []
            for doc in experiments:
                data = doc.to_dict()
                stats['total_experiments'] += 1
                
                if data.get('overall_score'):
                    scores.append(data['overall_score'])
                    stats['best_score'] = max(stats['best_score'], data['overall_score'])
                
                gen = data.get('generation', 0)
                stats['generation_counts'][gen] = stats['generation_counts'].get(gen, 0) + 1
            
            if scores:
                stats['average_score'] = sum(scores) / len(scores)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get generation stats: {str(e)}")
            return {}

# Singleton instance for global access
firebase_orchestrator = None

def init_firebase(service_account_path: str = None, storage_bucket: str = None):
    """Initialize global Firebase orchestrator"""
    global firebase_orchestrator
    firebase_orchestrator = FirebaseOrchestrator(service_account_path, storage_bucket)
    return firebase_orchestrator