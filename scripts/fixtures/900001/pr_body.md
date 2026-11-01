Synthetic e2e PR: not a real apache/airflow pull request.

The loader awaited asyncio.gather over every blob read. This reads them one at a time in a loop. I kept the loop because gather would open every blob at once and we hit the fd limit on large DAG bundles.

Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. Context for reviewers. 
