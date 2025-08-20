let shouldFail = false;

export function enableFailure(v: boolean) {
  shouldFail = v;
}

export function failureEnabled() {
  return shouldFail;
}
