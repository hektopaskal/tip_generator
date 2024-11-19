import mariadb
import sys
import pandas as pd
from pathlib import Path
import typer
from typing import Optional

# for similarity search with sentence embedding:
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from scipy.cluster.hierarchy import dendrogram, linkage
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter

# Create a Typer app
app = typer.Typer()


# insert a csv table into mariadb TODO: user, password, host, ... as parameter
@app.command()
def insert_data_from_csv_command(csv_file_path: str = typer.Argument(..., help="Path to csv file")):
    """Give Path to csv_file and insert data from a CSV file into MariaDB."""
    csv_file_path = Path(csv_file_path)

    try:
        connection = mariadb.connect(
            user="root",
            password="rootpw",
            host="localhost",  # or 127.0.0.1
            port=3306,  # default mariadb port
            database="pt_recommender_db"
        )
        print("Connection successful!")
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB: {e}")
        sys.exit(1)

    cursor = connection.cursor()

    df = pd.read_csv(csv_file_path)
    df = df.astype(str)

    for _, row in df.iterrows():  # _ is index
        sql_query = "INSERT INTO pt_recommendations (Tip, Information, Category, Goal, Focus, Activity_type, Daytime, Weekday, Validity_Flag, Weather, Concerns, AuthorsPaperCountCitationCount, citationCount, fieldsOfStudy, influentialCitationCount, publicationDate, publicationTypes, publicationVenue, referenceCount, title, tldr, url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        cursor.execute(sql_query, tuple(row))

    connection.commit()
    cursor.close()
    connection.close()

    print("Data inserted successfully!")

# Find similar recommendations via sentence embeddings
@app.command()
def find_similarities_command(
    user: str = typer.Argument(..., help="MariaDB username"),
    password: str = typer.Argument(..., help="MariaDB password"),
    host: str = typer.Argument(..., help="Database host"),
    port: int = typer.Argument(..., help="Database port"),
    database: str = typer.Argument(..., help="Database name"),
    threshold: Optional[float] = typer.Option(4, help="Threshold for clustering. Set to 4, if not specified")
):
    """Find tips that are semantically similar."""

    model = SentenceTransformer('paraphrase-MiniLM-L6-v2')
    try:
        connection = mariadb.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database
        )
        print("Connection successful!")
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB: {e}")
        sys.exit(1)

    cursor = connection.cursor()
    cursor.execute("SELECT ID, Tip FROM pt_recommendations")
    tips = cursor.fetchall()

    # Create DataFrame with 'Tip' and '#' (index) columns
    tips_df = pd.DataFrame(tips, columns=["ID", "Tip"])

    recommendations = tips_df["Tip"].tolist()

    embeddings = model.encode(recommendations)

    # Perform Agglomerative Clustering
    agg_clustering = AgglomerativeClustering(
        n_clusters=None, distance_threshold=threshold, linkage='ward')
    labels = agg_clustering.fit_predict(embeddings)

    # Create a DataFrame to hold the cluster labels and their corresponding indices
    tips_df['Cluster'] = labels

    # Group by cluster and get the indices of tips in each cluster
    clustered_tips = tips_df.groupby(
        'Cluster')['ID'].apply(list).reset_index()

    # Display the clusters with their corresponding IDs
    print(clustered_tips)
    print("_------------------------------------------")
    # Count the number of elements in each cluster
    cluster_counts = Counter(labels)

    # Find clusters with more than one element
    valid_clusters = [cluster for cluster,
                      count in cluster_counts.items() if count > 1]

    # Filter embeddings and labels to include only the valid clusters
    filtered_embeddings = []
    filtered_labels = []
    filtered_ids = []

    for i, label in enumerate(labels):
        if label in valid_clusters:
            filtered_embeddings.append(embeddings[i])
            filtered_labels.append(label)
            filtered_ids.append(tips_df.iloc[i]['ID'])

    filtered_embeddings = np.array(filtered_embeddings)
    filtered_labels = np.array(filtered_labels)
    filtered_ids = np.array(filtered_ids)

    # Display clusters with IDs
    for i in np.unique(filtered_labels):
        print(f"\nCluster {i}:")
        for idx, label in enumerate(filtered_labels):
            if label == i:
                print(f" - ID: {filtered_ids[idx]}, Tip: {recommendations[idx]}")

    cursor.close()
    connection.close()

    sys.exit(0)


if __name__ == "__main__":
    app()