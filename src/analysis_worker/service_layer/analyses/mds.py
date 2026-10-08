"""
Metric multidimensional scaling of the CONTINUOUS concept terms, standardised, on complete observations.
Optional clustering uses the same standardised observations.
"""
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist, squareform
from sklearn.cluster import KMeans
from sklearn.manifold import MDS

from analysis_worker.domain.model.job import AnalysisJob, AnalysisOutcome
from analysis_worker.service_layer.analyses.checks import insufficient, require_rows

DISTANCES = {
    'EUCLIDEAN': {'metric': 'euclidean'},
    'MANHATTAN': {'metric': 'cityblock'},
    'MINKOWSKI': {'metric': 'minkowski', 'p': 3},
}


def _clusters(data: np.ndarray, clustering: dict) -> list[str]:
    n_clusters = clustering['clusters']
    if n_clusters > len(data):
        raise insufficient(f"{n_clusters} clusters requested for {len(data)} observations", ['mds', 'clustering', 'clusters'])
    if clustering['method'] == 'KMEANS':
        labels = KMeans(n_clusters=n_clusters, n_init=10, random_state=0).fit_predict(data)
    else:
        labels = fcluster(linkage(data, method='ward'), t=n_clusters, criterion='maxclust') - 1
    return [str(int(label)) for label in labels]


def mds(job: AnalysisJob) -> AnalysisOutcome:
    frame = job.frame()
    columns = job.concept_columns('CONTINUOUS')
    data = frame[[c['name'] for c in columns]].dropna()
    dimensions = job.config['dimensions']
    require_rows(data, max(3, dimensions + 1), job, "MDS")

    sd = data.std(ddof=1)
    constant = [c for c in columns if not sd[c['name']] > 0]
    if len(constant) == len(columns):
        raise insufficient("All terms are constant across observations", job.spec_path + ['terms'])
    data = data.drop(columns=[c['name'] for c in constant])
    standardised = ((data - data.mean()) / data.std(ddof=1)).to_numpy()

    distances = squareform(pdist(standardised, **DISTANCES[job.config['distance']]))
    coordinates = MDS(
        n_components=dimensions, metric='precomputed', init='classical_mds', random_state=0
    ).fit_transform(distances)

    clustering = job.config.get('clustering')
    cluster_ids = _clusters(standardised, clustering) if clustering else [None] * len(data)

    observations = [
        {
            'group': job.observations[i]['group'],
            'record_ids': job.observations[i]['record_ids'],
            'coordinates': [float(x) for x in point],
            'cluster_id': cluster_id
        }
        for i, point, cluster_id in zip(data.index, coordinates, cluster_ids)
    ]
    return AnalysisOutcome(result={'observations': observations})
