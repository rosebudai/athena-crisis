// Heal-on-attack mod: attacking units heal 20 HP after attacking (if they survived).
AthenaEngine.on('afterAttack', function (ctx) {
  if (!ctx.source || ctx.source.health <= 0) {
    return;
  }

  return [
    {
      type: 'HealUnit',
      position: ctx.source.position,
      amount: 20,
    },
  ];
});

console.log('[Mod] Heal-on-attack enabled: units heal 20 HP after attacking');
