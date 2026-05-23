/**
 * No-op MSW server stub for Jest.
 *
 * Component unit tests are presentational and do not make API calls,
 * so a full msw/node setup is unnecessary and causes ESM-only dependency
 * issues (rettime, until-async). This stub exposes the same interface
 * (listen / resetHandlers / close / use) as a real SetupServer.
 */
export const server = {
  listen: jest.fn(),
  resetHandlers: jest.fn(),
  close: jest.fn(),
  use: jest.fn(),
};
