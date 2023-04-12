import random
import pytest

from .helpers.helpers import request_with_validation
from .helpers.collection_setup import drop_collection

collection_name = 'test_collection'


@pytest.fixture(autouse=True)
def setup():
    multivec_collection_setup(collection_name=collection_name)
    yield
    drop_collection(collection_name=collection_name)


def multivec_collection_setup(collection_name='test_collection', on_disk_payload=False):
    response = request_with_validation(
        api='/collections/{collection_name}',
        method="DELETE",
        path_params={'collection_name': collection_name},
    )
    assert response.ok

    response = request_with_validation(
        api='/collections/{collection_name}',
        method="PUT",
        path_params={'collection_name': collection_name},
        body={
            "vectors": {
                "image": {
                    "size": 4,
                    "distance": "Dot",
                    "hnsw_config": {
                        "m": 20,
                    }
                },
                "audio": {
                    "size": 4,
                    "distance": "Dot",
                    "hnsw_config": {
                        "ef_construct": 100
                    },
                    "quantization_config": {
                        "scalar": {
                            "type": "int8",
                            "quantile": 0.6
                        }
                    }
                },
                "text": {
                    "size": 8,
                    "distance": "Cosine",
                    "quantization_config": {
                        "scalar": {
                            "type": "int8",
                            "always_ram": True
                        }
                    }
                }
            },
            "hnsw_config": {
                "m": 10,
                "ef_construct": 80
            },
            "quantization": {
                "scalar": {
                    "type": "int8",
                    "quantile": 0.5
                }
            },
            "on_disk_payload": on_disk_payload
        }
    )
    assert response.ok

    response = request_with_validation(
        api='/collections/{collection_name}/points',
        method="PUT",
        path_params={'collection_name': collection_name},
        query_params={'wait': 'true'},
        body={
            "points": [
                {
                    "id": 1,
                    "vector": {
                        "image": [0.05, 0.61, 0.76, 0.74],
                        "audio": [0.05, 0.61, 0.76, 0.74],
                        "text": [0.05, 0.61, 0.76, 0.74, 0.05, 0.61, 0.76, 0.74],
                    },
                    "payload": {"city": "Berlin"}
                },
                {
                    "id": 2,
                    "vector": {
                        "image": [0.19, 0.81, 0.75, 0.11],
                        "audio": [0.19, 0.81, 0.75, 0.11],
                        "text": [0.19, 0.81, 0.75, 0.11, 0.19, 0.81, 0.75, 0.11],
                    },
                    "payload": {"city": ["Berlin", "London"]}
                }
            ]
        }
    )
    assert response.ok


def test_retrieve_vector_specific_hnsw():
    response = request_with_validation(
        api='/collections/{collection_name}',
        method="GET",
        path_params={'collection_name': collection_name},
    )
    assert response.ok

    config = response.json()['result']['config']
    vectors = config['params']['vectors']
    assert vectors['image']['hnsw_config']['m'] == 20
    assert 'ef_construct' not in vectors['image']['hnsw_config']
    assert 'm' not in vectors['audio']['hnsw_config']
    assert vectors['audio']['hnsw_config']['ef_construct'] == 100
    assert 'hnsw_config' not in vectors['text']
    assert config['hnsw_config']['m'] == 10
    assert config['hnsw_config']['ef_construct'] == 80


def test_retrieve_vector_specific_quantization():
    response = request_with_validation(
        api='/collections/{collection_name}',
        method="GET",
        path_params={'collection_name': collection_name},
    )
    assert response.ok

    config = response.json()['result']['config']
    vectors = config['params']['vectors']
    assert 'quantization_config' not in vectors['image']
    assert vectors['audio']['quantization_config']['scalar']['type'] == "int8"
    assert vectors['audio']['quantization_config']['scalar']['quantile'] == 0.6
    assert 'always_ram' not in vectors['audio']['quantization_config']['scalar']
    assert vectors['text']['quantization_config']['scalar']['type'] == "int8"
    assert 'quantile' not in vectors['text']['quantization_config']['scalar']
    assert vectors['text']['quantization_config']['scalar']['always_ram']
    assert config['quantization_config']['scalar']['type'] == "int8"
    assert config['quantization_config']['scalar']['quantile'] == 0.5

@pytest.mark.skip(reason="Takes too long for a sanity test")
def test_disable_indexing():
    indexed_name = 'test_collection_indexed'
    unindexed_name = 'test_collection_unindexed'
    
    response = request_with_validation(
        api='/collections/{collection_name}',
        method="DELETE",
        path_params={'collection_name': indexed_name},
    )
    assert response.ok
    
    response = request_with_validation(
        api='/collections/{collection_name}',
        method="DELETE",
        path_params={'collection_name': unindexed_name},
    )
    assert response.ok

    def create_collection(collection_name, indexing_threshold):
        response = request_with_validation(
            api='/collections/{collection_name}',
            method="PUT",
            path_params={'collection_name': collection_name},
            body={
                "vectors": {
                    "size": 256,
                    "distance": "Dot",
                },
                "optimizers_config": {
                    "indexing_threshold": indexing_threshold
                }
            }
        )
        assert response.ok
        
    amount_of_vectors = 3000
    
    # Collection with indexing enabled
    create_collection(indexed_name, 1000)
    insert_vectors(indexed_name, amount_of_vectors)
    
    # Collection with indexing disabled
    create_collection(unindexed_name, None)
    insert_vectors(unindexed_name, amount_of_vectors)
    
    # Get info
    response = request_with_validation(
        method='GET',
        api='/collections/{collection_name}',
        path_params={'collection_name': indexed_name},
    )
    assert response.ok
    assert response.json()['result']['indexed_vectors_count'] > 0
    assert response.json()['result']['vectors_count'] == amount_of_vectors
    
    # Get info
    response = request_with_validation(
        method='GET',
        api='/collections/{collection_name}',
        path_params={'collection_name': unindexed_name},
    )
    assert response.ok
    assert response.json()['result']['indexed_vectors_count'] == 0
    assert response.json()['result']['vectors_count'] == amount_of_vectors
    
    
def insert_vectors(collection_name='test_collection', count=2000):

    ids = [x for x in range(count)]
    vectors = [[random.random() for _ in range(256)] for _ in range(count)]
    
    response = request_with_validation(
        api='/collections/{collection_name}/points',
        method='PUT',
        path_params={'collection_name': collection_name},
        query_params={'wait': 'true'},
        body={
            "batch": {
                "ids": ids,
                "vectors": vectors,
            }
        }
    )
    assert response.ok
    
    
    