
# %%
import os
import json
import csv

def extract_nodes_from_json(data, keys_of_interest, found=None):
    if found is None:
        found = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in keys_of_interest:
                found.append((k, json.dumps(v, sort_keys=True)))
            if isinstance(v, str):
                try:
                    nested = json.loads(v)
                    extract_nodes_from_json(nested, keys_of_interest, found)
                except:
                    pass
            else:
                extract_nodes_from_json(v, keys_of_interest, found)
    elif isinstance(data, list):
        for item in data:
            extract_nodes_from_json(item, keys_of_interest, found)
    return found

def clean_root_folder_name(folder_name):
    if folder_name.endswith(".Report"):
        return folder_name[:-7]  # Remove last 7 chars, i.e., ".Report"
    return folder_name

def analyze_multiple_pbip_folders(parent_folder):
    keys_of_interest = {"Entity", "Property", "queryRef"}
    unique_items = set()

    for root_folder_name in os.listdir(parent_folder):
        root_folder_path = os.path.join(parent_folder, root_folder_name)
        if os.path.isdir(root_folder_path):
            clean_name = clean_root_folder_name(root_folder_name)
            for dirpath, _, filenames in os.walk(root_folder_path):
                for filename in filenames:
                    if filename.lower().endswith(".json"):
                        filepath = os.path.join(dirpath, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                            found_nodes = extract_nodes_from_json(json_data, keys_of_interest)
                            for k, v in found_nodes:
                                unique_items.add((clean_name, root_folder_name, k, v))
                        except Exception as e:
                            print(f"Error processing {filepath}: {e}")

    # Convert set to list of dicts for CSV export
    results = []
    for root, folder, node, value in unique_items:
        results.append({"root": root, "folder": folder, "node": node, "value": value})

    return results

def save_results_to_csv(data, output_file):
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['root', 'folder', 'node', 'value']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)

# Example usage
if __name__ == "__main__":
    parent_folder_path = "reports"
    output_csv_path = "extracted_metadata.csv"
    results = analyze_multiple_pbip_folders(parent_folder_path)
    save_results_to_csv(results, output_csv_path)
    print(f"Analyzed parent folder: {os.path.basename(parent_folder_path)}")
    print(f"Total unique items found: {len(results)}")
    print(f"Results saved to {output_csv_path}")



# %%
