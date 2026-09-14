/** Share an in-flight refresh so older overlapping responses cannot overwrite new state. */
export function singleFlightRefresh(refresh: () => Promise<void>) {
  let pending: Promise<void> | null = null;
  return () => {
    if (!pending) pending = Promise.resolve().then(refresh).finally(() => { pending = null; });
    return pending;
  };
}
