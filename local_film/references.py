"""Shared creative guidance for planning and character-reference conditioning."""

def character_reference_guidance(value):
 if value<=0:return ''
 if value<=33:
  direction='Keep the referenced person readily recognizable, including facial identity and key appearance. Allow subtle pose, expression and lighting changes needed by the brief.'
 elif value<=66:
  direction='Keep a recognizable likeness to the referenced person. Allow hairstyle, clothing, pose, setting and expression changes where the brief requests them; do not copy the reference framing.'
 else:
  direction='Use the referenced adult character as loose inspiration. Facial features and styling may be reinterpreted to create a distinct adult character that follows the brief.'
 return f'Character reference creative guidance: {value:g}/100. {direction} Preserve explicit instructions; do not invent unrelated appearance changes. Keep the resulting character consistent within this shot and its continuations.'
