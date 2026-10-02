/** Logging out must always work from the user's point of view: if the server call fails
 *  (network or 5xx), we still drop the local session state so the login page shows. The
 *  server-side session then simply expires (7 days). Never throws. */
export async function signOut(request: () => Promise<unknown>, clearLocal: () => void): Promise<void> {
  try {
    await request()
  } catch (err) {
    console.warn('logout request failed; signing out locally', err)
  }
  clearLocal()
}
