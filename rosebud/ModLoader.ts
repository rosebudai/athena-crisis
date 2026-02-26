export async function loadMods(): Promise<void> {
  let response: Response;
  try {
    response = await fetch('mods.json');
  } catch {
    console.log('[ModLoader] No mods.json found, skipping mods');
    return;
  }

  if (!response.ok) {
    console.log('[ModLoader] No mods.json found, skipping mods');
    return;
  }

  let manifest: unknown;
  try {
    manifest = await response.json();
  } catch {
    console.warn('[ModLoader] Invalid mods.json, skipping mods');
    return;
  }

  if (
    typeof manifest !== 'object' ||
    manifest === null ||
    !Array.isArray((manifest as { mods?: unknown }).mods)
  ) {
    console.warn('[ModLoader] Invalid mods.json, skipping mods');
    return;
  }

  const mods = (manifest as { mods: Array<string> }).mods;
  if (mods.length === 0) {
    return;
  }

  let loaded = 0;
  for (const modPath of mods) {
    let modResponse: Response;
    try {
      modResponse = await fetch(modPath);
    } catch {
      console.warn('[ModLoader] Failed to fetch mod:', modPath);
      continue;
    }

    if (!modResponse.ok) {
      console.warn('[ModLoader] Failed to fetch mod:', modPath);
      continue;
    }

    const source = await modResponse.text();

    try {
      new Function(source)();
      loaded++;
    } catch (error) {
      console.error('[ModLoader] Error executing mod:', modPath, error);
    }
  }

  console.log(`[ModLoader] Loaded ${loaded} mod(s)`);
}
