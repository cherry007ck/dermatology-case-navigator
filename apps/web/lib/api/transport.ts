// Transport interface and error type shared by the live client and the fixture mock.
import type {
  AdvanceRequest,
  AdvanceResult,
  AppendTurnsRequest,
  ApiErrorResponse,
  ClinicianNote,
  ClinicianNoteRequest,
  CollectionsResponse,
  ConfirmRequest,
  CorrectionRequest,
  CreateSessionRequest,
  CreateSessionResponse,
  ReadinessResponse,
  SessionSnapshot,
  SkipQuestionRequest,
} from "./types";

export type ApiMode = "live" | "mock";

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }

  static fromBody(status: number, body: ApiErrorResponse): ApiRequestError {
    return new ApiRequestError(status, body.error.code, body.error.message, body.error.retryable);
  }
}

/** Mirrors docs/03-api-contract.md routes one-to-one. */
export interface ApiTransport {
  readonly mode: ApiMode;
  readiness(demoCode: string): Promise<ReadinessResponse>;
  listCollections(demoCode: string): Promise<CollectionsResponse>;
  createSession(demoCode: string, body: CreateSessionRequest): Promise<CreateSessionResponse>;
  getSession(sessionId: string, token: string): Promise<SessionSnapshot>;
  appendTurns(sessionId: string, token: string, body: AppendTurnsRequest): Promise<SessionSnapshot>;
  advance(sessionId: string, token: string, body: AdvanceRequest): Promise<AdvanceResult>;
  skip(sessionId: string, token: string, body: SkipQuestionRequest): Promise<SessionSnapshot>;
  confirm(sessionId: string, token: string, body: ConfirmRequest): Promise<SessionSnapshot>;
  correct(sessionId: string, token: string, body: CorrectionRequest): Promise<SessionSnapshot>;
  addClinicianNote(sessionId: string, token: string, body: ClinicianNoteRequest): Promise<ClinicianNote>;
}
