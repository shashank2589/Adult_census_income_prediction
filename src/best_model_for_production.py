from retrieve_data import read_params
import argparse
import pickle
import mlflow
from mlflow.tracking import MlflowClient
from pprint import pprint

def best_model_for_production(config_path):
    config = read_params(config_path)
    mlflow_config = config["mlflow_config"]
    remote_server_uri = mlflow_config["remote_server_uri"]
    
    # Set the tracking URI to connect to the remote server
    mlflow.set_tracking_uri(remote_server_uri)
    
    # Create an MLflow client
    mlflow_client = MlflowClient()
    
    # Define the experiment ID
    experiment_id = 1
    
    # Retrieve all runs from the specified experiment
    runs = mlflow.search_runs(experiment_ids=[experiment_id])
    
    # Find the run with the highest ROC AUC score
    best_run = runs.loc[runs['metrics.roc_auc_score'].idxmax()]
    
    # Get the ROC AUC score of the best run
    best_roc_auc_score = best_run['metrics.roc_auc_score']
    
    # Get the run ID of the best run
    best_run_id = best_run['run_id']

    # Retrieve the best run's metadata
    best_run_info = mlflow_client.get_run(run_id=best_run_id)

    # Extract the model_name parameter from the metadata
    best_model_name = best_run_info.data.params['model_name']
    
    # Define the destination directory for the model
    model_directory = config["model"]["saved_model"]
    
    # Check if the ROC AUC score is highest
    if best_roc_auc_score > config["roc_auc"]["threshold"]:
        # Load the best model using the run ID
        best_model = mlflow.sklearn.load_model(f"runs:/{best_run_id}/model")
        
        model_version = 1
        # Dump the best model in pickle format
        with open(f"{model_directory}", "wb") as model_file:
            pickle.dump(best_model, model_file)
        
        # Set the model to "production" stage
        mlflow_client.transition_model_version_stage(
            name=best_model_name,
            version=model_version,
            stage="Production"
        )
        
        # Print the details of the best model
        print("Best Model for Production:")
        pprint({
            "Run ID": best_run_id,
            "Model Version": model_version,
            "Model Name" : best_model_name,
            "ROC AUC Score": best_roc_auc_score,
            "Model Stage": "Production",
            "Model Path": f"{model_directory}"
        })
        # Transition other models to "Staging" stage
        for _, row in runs.iterrows():
            run_id = row['run_id']
            model_name = mlflow.get_run(run_id).data.params['model_name']
            if model_name != best_model_name:
                mlflow_client.transition_model_version_stage(
                    name=model_name,
                    version=model_version,
                    stage="Staging"
                )
            else:
                print("No models meet the ROC AUC score threshold for production.")

if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--config", default="params.yaml")
    parsed_args = args.parse_args()
    best_model_for_production(config_path=parsed_args.config)
