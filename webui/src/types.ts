export type ModuleType = "analyst" | "researcher" | "trader" | "risk" | "dataflow" | "config" | "cli";

export type ModuleRecord = {
  name: string;
  path: string;
  type: ModuleType;
  description: string;
  inputs: string[];
  outputs: string[];
  dependencies: string[];
  risks: string[];
  related_files: string[];
};
