var heavyId = AthenaEngine.registerUnit({
  base: 'Infantry',
  name: 'Heavy Infantry',
  overrides: {
    cost: 300,
    defense: 20,
    vision: 2,
  },
});
console.log('[Mod] Registered Heavy Infantry with ID:', heavyId);
