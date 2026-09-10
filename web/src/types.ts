export type ArtifactKind = "source_card" | "table" | "chart" | "report";
export type ArtifactStatus = "active" | "superseded";

export type Artifact = {
  id: string;
  kind: ArtifactKind;
  status: ArtifactStatus;
  superseded_by?: string | null;
  supersede_reason?: string | null;
  title: string;
  subtitle?: string | null;
  provenance?: Record<string, unknown>;
  payload: Record<string, unknown>;
  revision?: number;
  updated_at?: string;
};

export type Progress = {
  id: string;
  label: string;
  status: "running" | "done";
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  progress: Progress[];
  reasoning?: string;
  streaming?: boolean;
  stopped?: boolean;
};

export type DeskEvent = {
  type: string;
  [key: string]: unknown;
};

export type BoardDisplay = {
  showReport: boolean;
  turn: number;
  activeReportId?: string | null;
};

export type Citation = {
  n: number;
  url?: string;
  title?: string;
  id?: string;
  publisher?: string;
  as_of?: string;
  note?: string;
};

export type ReportBlock = {
  type: string;
  [key: string]: unknown;
};
