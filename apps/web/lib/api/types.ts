// Named aliases over the generated OpenAPI types. Never hand-write response shapes:
// regenerate with `npm run generate:api` after contracts/openapi.json changes.
import type { components } from "./generated";

type S = components["schemas"];

export type SessionSnapshot = S["SessionSnapshot"];
export type AdvanceResult = S["AdvanceResult"];
export type Question = S["Question"];
export type Turn = S["Turn"];
export type TurnInput = S["TurnInput"];
export type PatientFact = S["PatientFact"];
export type EvidenceRef = S["EvidenceRef"];
export type Brief = S["Brief"];
export type BriefItem = S["BriefItem"];
export type CaseCard = S["CaseCard"];
export type CaseAttribution = S["CaseAttribution"];
export type Passage = S["Passage"];
export type CaseChange = S["CaseChange"];
export type SearchVersion = S["SearchVersion"];
export type SupportedStatement = S["SupportedStatement"];
export type Collection = S["Collection"];
export type CollectionsResponse = S["CollectionsResponse"];
export type ReadinessResponse = S["ReadinessResponse"];
export type CreateSessionRequest = S["CreateSessionRequest"];
export type CreateSessionResponse = S["CreateSessionResponse"];
export type AppendTurnsRequest = S["AppendTurnsRequest"];
export type AdvanceRequest = S["AdvanceRequest"];
export type SkipQuestionRequest = S["SkipQuestionRequest"];
export type ConfirmRequest = S["ConfirmRequest"];
export type CorrectionRequest = S["CorrectionRequest"];
export type ClinicianNoteRequest = S["ClinicianNoteRequest"];
export type ClinicianNote = S["ClinicianNote"];
export type ApiErrorResponse = S["ApiErrorResponse"];
