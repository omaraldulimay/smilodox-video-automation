"""Seed prompt templates provided by the team (Zalando upper/lower garment campaigns).

NOTE on resolution_min (RESOLVED 2026-08-20 against the real Zalando Partner
University "Zalando video guidelines" page): Zalando does NOT require a fixed 9:16 --
its actual spec is "aspect ratio (height/width): 1.44 to 1.8" with a minimum of
762x1100px. 762x1100 -> height/width = 1100/762 = 1.443 (the lower bound / minimum
size). 1080x1920 (9:16) -> height/width = 1920/1080 = 1.778, which is inside the same
1.44-1.8 range and well above the minimum pixel count. So there never was a real
conflict -- 762x1100 is Zalando's minimum, 1080x1920 is our actual target, both are
independently valid points on Zalando's allowed range. `aspect_ratio: "9:16"` in the
JSON below is correct and Zalando-compliant.

NOTE on duration (checked against the same source, 2026-08-20): Zalando's own
guidance is "ideally 15 seconds, but edits can sit between 12-18 seconds" -- worded as
a recommendation, not a hard cutoff, so this is advisory rather than a stated pass/
fail requirement. Per explicit team decision, `duration_seconds` stays at the current
value below rather than being raised toward 15s (that would also raise per-clip
credit cost ~50%). Flagging as residual risk: our clips run below Zalando's stated
12-18s comfort range, and the source text doesn't fully rule out the review/upload
tooling itself rejecting shorter clips -- worth reconfirming once real uploads are
tested, but not blocking the current pipeline.

NOTE on other Zalando technical/content requirements added 2026-08-20: file format
(MP4, H.264, min 24fps, min 2000 Kb/s bitrate, max 250MB, one JPEG preview thumbnail
per video, no PNG), and content restrictions (no minors, no nudity/exposed intimate
areas, no violence/weapons, no discriminatory/political/religious content, no
substance use, no on-screen text or sound) are captured in each prompt's
`zalando_compliance` block and the corresponding `negative_prompt` entries below.

NOTE on Kling 3.0 variants: unlike the 4-image templates, Kling only gets 2 reference
images (start_image/end_image), so its shots reuse start_image for both shot 1 and
the shot-2 close-up (a tighter static crop, not a new photo) -- there is no dedicated
detail reference for Kling. All four templates use hard cuts, no camera movement
(matches the team's requirement that the cut style stay consistent for Zalando PDP
acceptance).

NOTE on UNTERTEIL_PROMPT: originally received in a different JSON schema (
`zalando_global_settings`), 8s/2-shots, incomplete (cut off mid SHOT_02, no
negative_prompt), with an explicitly "flirtatious/suggestive" presentation_style.
Per team request (2026-08-20) it has been restructured to mirror OBERTEIL_PROMPT
exactly: same schema, same 10s/4-shot/2.5s-per-shot timing, same camera/model rules,
same negative_prompt list -- content adapted for the lower garment (waistband/
pockets/hem in product_lock, shot framing widened to keep feet in frame). The tone
was also normalized from "flirtatious" to Oberteil's neutral "relaxed, confident" --
a judgment call made to (a) match the explicit "align it with Oberteil" request and
(b) remove a real content-policy risk (Higgsfield generation fails permanently on
`nsfw`/`ip_detected`). Revert to a more suggestive tone only if the team confirms
they want that specifically for the lower-garment line.
"""

OBERTEIL_PROMPT = r"""{
 "campaign": "zalando_upper_garment_video",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando guidance recommends approximately 15 seconds, with 12-18 seconds stated as the preferred editing range. This campaign intentionally uses the 10-second format set below.",
 "content_restrictions": "adult model only, shown fully dressed in the reference garments at all times with no additional skin exposure beyond the garments' own design; no combat implements or physical altercation of any kind; no discriminatory, political or religious content; no substance use; no on-screen text or sound"
 },
 "video_spec": {
 "aspect_ratio": "9:16",
 "resolution_min": "762x1100",
 "fps": 24,
 "duration_seconds": 10,
 "shot_count": 4,
 "shot_duration_seconds": 2.5,
 "editing": "hard cuts only, no transitions",
 "audio_text_graphics": "none"
 },
 "reference_images": {
 "image1": {
 "role": "model identity, body proportions, full front silhouette, front garment geometry and overall color",
 "content": "full body, front view"
 },
 "image2": {
 "role": "upper-garment material, fabric texture, neckline, sleeves, seams, front print and logo detail",
 "content": "close-up of upper garment"
 },
 "image3": {
 "role": "rear garment geometry, rear construction, rear print and label detail",
 "content": "back view"
 },
 "image4": {
 "role": "hero detail, micro-texture and exact stitching, hardware, logo or print detail for the final shot",
 "content": "product detail shot"
 }
 },
 "product_lock": {
 "rule": "All images labeled image1-image4 show the SAME physical upper garment. Match color, cut, fabric, texture, print, logo and construction exactly to the relevant reference roles in every shot. Never redesign, simplify or invent details. Never hallucinate, invent or substitute a different fabric knit, weave, ribbing, sheen or surface texture than what is actually visible in the reference photos -- the rendered fabric must be recognizably the exact same physical material shown there, not a generic or plausible-looking substitute. No unintended color drift, blotching, flicker or discoloration. Match the color saturation and vibrancy of the reference photos exactly -- never render the garment flatter, greyer, duller or less saturated than it appears there, even against the darker studio backdrop; the fabric's true color intensity must read the same as in the references. Preserve all intentional washes, gradients, fading, distressing, melange effects and color variation exactly as shown in the references. Any brand tags, labels or logos visible in the references -- however small -- must be reproduced with their printed mark or graphic intact, legible and at the same relative size and position; never render a logo tag as a blank, empty or plain-colored patch. Match the same number of tags/marks as the references, never duplicated. For any printed or textured pattern (e.g. animal print, camo, stripes, florals, marbling), take the pattern's exact scale, shape, spacing and colors directly from the reference photos -- never substitute a different, generic, smoothed-over or invented pattern.",
 "primary_product": "upper garment — always the dominant commercial focus, and the ONLY product this template defines (image1-image4). The full outfit shown is not the product: the lower garment/shoes are a separately-sold Smilodox product, present only as styling context (a different video job if it needs its own accurate treatment). It should still look natural and consistent; if its own logo is already clearly legible in the references, keep it that way, but never infer, copy or invent branding for it from the upper garment, and never treat the full outfit as one branded unit."
 },
 "brand_identity": {
 "default_style": "The brand's icon, when present, is a minimal angular feline head in left-facing profile (sharp straight edges, no curves, no mouth or fang; an angular ear-spike on top; a twin-stroke swept-back mane tapering to points on the right). The wordmark, when present, is \"SMILODOX\" in bold, condensed, all-caps geometric sans-serif. CRITICAL: a single product carries EITHER the icon OR the wordmark, NEVER both together -- match whichever this product's own image1-image4 actually show (icon-only, text-only, or no branding at all); never invent the other one or add either that isn't literally visible here.",
 "no_invention_rule": "If no brand tag, label or logo graphic is visible anywhere in image1-image4, do not add one — some garments carry no visible branding at all. Different products in this same brand legitimately carry different mark styles (icon+tag vs. plain text vs. none) -- never copy the mark style from a different, previously-seen product onto this one."
 },
 "camera_and_environment": {
 "camera": "camera remains completely locked within each shot, with no zoom, pan, tilt, dolly, tracking, shake or drift; camera position, lens and framing may differ only between shots as explicitly defined",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting across all shots",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout all 4 shots -- her face (bone structure, eyes, nose, mouth, skin tone) must exactly match the real person shown in the reference photos; never generate a different-looking, generic or stylized face, and never let facial identity drift between shots",
 "skin_texture": "real human skin, not airbrushed or beautified -- visible natural micro-texture (fine pores, subtle unevenness in tone, natural sheen that varies with light and movement, faint natural blemishes or texture where the reference photos show them). Skin should look photographed, not digitally smoothed, painted, waxy or plastic; avoid a uniform matte or porcelain surface.",
 "expression": "relaxed, confident, subtle natural smile; direct eye contact in front-facing shots; in profile shots the head and gaze remain naturally aligned with the body orientation; calm, natural blink rate with eyes mostly open and steady -- no rapid, repeated or fluttering blinking; eyes look natural, alive and light-reflective, with normal moisture and catchlights -- never glassy, doll-like, dead-eyed, cross-eyed or artificial-looking",
 "feet_rule": "feet remain naturally grounded and stable; a repositioning foot may lift minimally in a biomechanically natural step before planting fully — no tiptoes, floating feet or sustained heel lifting",
 "movement_rule": "only the choreography defined per shot — no improvised movement"
 },
 "aesthetic_direction": "Premium minimalist PDP fashion aesthetic with subtle editorial polish, consistent with a single cohesive brand shoot. Fabric drapes softly and catches light naturally, emphasizing premium tactile material quality. Same posture energy and framing logic across all generations.",
 "consistency_control": {
 "tolerance": "Generations across different products should look like they belong to the same campaign/shoot — same energy, same framing logic, same pacing. They do not need to be pixel-identical.",
 "fixed_across_generations": ["camera framing per shot", "choreography timing", "lighting setup", "background", "pose sequence logic"],
 "allowed_to_vary_naturally": ["exact micro-timing of fabric movement", "minor natural body motion", "product-specific garment appearance from references"],
 "seed_instruction": "Reuse the same seed value across all product generations if Higgsfield supports seed input, to minimize unwanted variance in pose, framing or lighting interpretation."
 },
 "choreography_discipline": "Timing windows below (e.g. 0.0-0.5s) are fixed and repeat consistently across generations; only the fabric's visual texture may vary. WITHIN a single shot, motion flows continuously through that shot's own windows -- no speeding into a pose then freezing at a window boundary. This applies ONLY inside each shot, NOT between shots: every cut to the next shot is still a hard cut to that shot's own camera view (per the shot list below), never a continuation of the previous shot's move, and the model does not visibly rotate or reposition across the cut. Exception: shot_04_garment_detail is a deliberate total static hold (per its own choreography below) -- follow that instruction instead.",
 "shots": [
 {
 "id": "shot_01_front_full_body",
 "primary_product_reference": "image1",
 "supporting_reference_roles": ["image2 for upper-garment material and front detail", "image3 for construction continuity"],
 "view": "direct front, full body, both shoes visible, model centered",
 "framing": "maximize upper-garment visibility while maintaining comfortable, consistent small headroom and full shoe visibility; the complete garment, including its lowest hem, remains unobstructed and commercially prominent",
 "choreography": {
 "0.0-0.5s": "weight shifts naturally from left to right leg",
 "0.5-1.0s": "right leg becomes primary support, left knee soft and relaxed",
 "1.0-1.5s": "left foot repositions slightly outward and forward with a minimal natural step, then plants fully and remains stable",
 "1.5-2.5s": "settles into relaxed asymmetric stance, holds pose, subtle smile, direct eye contact"
 }
 },
 {
 "id": "shot_02_side_upper_garment",
 "primary_product_reference": "image2",
 "supporting_reference_roles": ["image1 for model identity, proportions, overall garment silhouette and color", "image3 for construction continuity where relevant"],
 "view": "exact 90-degree left side profile, upper garment dominates composition -- a closer, garment-focused crop than shot 1's full-body framing, not a repeat of it; head and gaze follow the profile orientation",
 "framing": "product-centered crop that keeps the entire upper garment from neckline and sleeves through its lowest hem fully visible, with a small amount of lower-body styling context; adapt the crop to garment length without cutting off the product",
 "choreography": {
 "0.0-0.5s": "weight shifts naturally from left to right leg",
 "0.5-1.0s": "right leg becomes primary support, knees remain relaxed",
 "1.0-1.5s": "subtle natural weight transfer with minimal torso response; garment remains clearly readable and profile alignment is preserved",
 "1.5-2.5s": "settles into final side-profile stance and holds pose with gaze aligned to the body"
 }
 },
 {
 "id": "shot_03_back_upper_garment",
 "primary_product_reference": "image3",
 "supporting_reference_roles": ["image1 for model identity, proportions and overall color", "image2 for fabric and construction continuity"],
 "view": "exact 180-degree rear view, upper garment dominates composition -- a closer, garment-focused crop than shot 1's full-body framing, not a repeat of it",
 "framing": "product-centered crop that keeps the entire upper garment, including sleeves and its lowest rear hem, fully visible, with a small amount of lower-body styling context; model centered and crop adapted to garment length",
 "choreography": {
 "0.0-0.5s": "weight shifts naturally from right to left leg",
 "0.5-1.0s": "left leg becomes primary support, right knee soft and relaxed",
 "1.0-1.5s": "right foot repositions slightly outward and back with a minimal natural step, then plants fully and remains stable",
 "1.5-2.5s": "settles into final rear stance and holds pose"
 }
 },
 {
 "id": "shot_04_garment_detail",
 "primary_product_reference": "image4",
 "supporting_reference_roles": ["image2 for material and texture continuity", "image1 and image3 for overall product identity"],
 "view": "tight locked-off close-up matching the exact detail shown in image4 — no body or camera movement, only extremely subtle fabric response",
 "framing": "composition matches image4 as closely as possible, with maximum sharpness on the exact product detail",
 "choreography": {
 "0.0-2.5s": "static hold, maximum sharpness on the exact garment detail"
 }
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking", "camera shake", "camera drift",
 "tiptoes", "sustained heel lifting", "floating feet", "foot sliding", "foot-ground penetration",
 "garment redesign", "garment morphing", "frame-to-frame garment morphing", "color drift", "logo drift", "blank logo tag", "missing logo graphic", "illegible logo", "invented print pattern", "altered print pattern", "generic pattern substitution", "invented details",
 "fabric hallucination", "invented fabric texture", "generic fabric substitution", "changed fabric knit or weave", "wrong fabric sheen",
 "different face", "generic face", "stylized face", "face identity drift", "face swap", "altered facial features", "different model",
 "desaturated colors", "muted colors", "washed-out color", "flattened color contrast", "dull or lifeless garment color",
 "jerky movement", "sudden pose snap", "abrupt motion", "staccato motion", "freeze-frame pause between movements", "hectic movement", "rushed weight shift",
 "model turning between shots", "body rotation carried across a cut", "continuous camera move across a cut", "full body framing in a product close-up shot",
 "invented logo icon", "added brand icon not shown in references", "invented tag graphic", "generic default logo substituted for actual mark", "logo style copied from a different product", "icon and wordmark combined on one garment", "curved or rounded logo icon shape", "roaring open-mouth logo face", "outfit treated as a single product", "branding copied across the full outfit", "duplicate logo tag", "extra brand tag not in references",
 "unintended fabric blotches or discoloration", "temporal texture instability", "fabric texture crawling", "unnatural fabric physics", "seam flicker", "hardware flicker",
 "motion blur on garment", "pixelation", "compression artifacts", "loss of product detail",
 "walking", "turning", "spinning", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion", "malformed hands", "extra or fused fingers", "artifacts where hands touch fabric or skin", "excessive blinking", "rapid eye blinking", "eye flutter", "glassy eyes", "doll-like eyes", "dead-eyed stare", "artificial eye look",
 "background morphing", "warped straight seams", "lens flare", "film grain", "vignette", "depth of field blur",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter", "airbrushed skin", "over-smoothed skin", "plastic skin", "waxy skin", "porcelain skin", "digitally painted skin", "uncanny smooth complexion",
 "non-adult appearance", "unintended skin exposure beyond garment design", "combat implements", "physical altercation",
 "discriminatory symbols", "religious imagery", "substance use", "hateful imagery"
 ]
}"""

# Restructured 2026-08-20 to mirror OBERTEIL_PROMPT's schema/timing/tone -- see module docstring.
# Revised again 2026-08-21 (user-supplied rewrite): fixes a physical contradiction in the old
# feet_rule (required feet to stay flat at all times while also asking a foot to slide), clarifies
# the camera rule to allow per-shot framing changes (locked only within a shot, not across all
# shots), protects intentional garment texture (washes/melange/fading) from being "corrected" away,
# adds framing language that prioritizes never cropping the garment, adds supporting_reference_roles
# per shot so model identity/consistency threads through from image1 even when a shot's primary
# reference is a different image, and expands negative_prompt with more specific known AI-video
# failure modes (foot-ground penetration, garment morphing, seam/hardware flicker, etc).
UNTERTEIL_PROMPT = r"""{
 "campaign": "zalando_lower_garment_video",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando guidance recommends approximately 15 seconds, with 12-18 seconds stated as the preferred editing range. This campaign intentionally uses the 10-second format set below.",
 "content_restrictions": "adult model only, shown fully dressed in the reference garments at all times with no additional skin exposure beyond the garments' own design; no combat implements or physical altercation of any kind; no discriminatory, political or religious content; no substance use; no on-screen text or sound"
 },
 "video_spec": {
 "aspect_ratio": "9:16",
 "resolution_min": "762x1100",
 "fps": 24,
 "duration_seconds": 10,
 "shot_count": 4,
 "shot_duration_seconds": 2.5,
 "editing": "hard cuts only, no transitions",
 "audio_text_graphics": "none"
 },
 "reference_images": {
 "image1": {
 "role": "model identity, body proportions, full front silhouette, front garment geometry and overall color",
 "content": "full body, front view"
 },
 "image2": {
 "role": "lower-garment material, fabric texture, waistband, rise, seams, pockets, front print and logo detail",
 "content": "close-up of lower garment"
 },
 "image3": {
 "role": "rear garment geometry, rear construction, back pockets, rear print and label detail",
 "content": "back view"
 },
 "image4": {
 "role": "hero detail, micro-texture and exact stitching, hardware, logo or print detail for the final shot",
 "content": "product detail shot"
 }
 },
 "product_lock": {
 "rule": "All images labeled image1-image4 show the SAME physical lower garment. Match color, cut, fabric, texture, print, logo and construction exactly to the relevant reference roles in every shot. Never redesign, simplify or invent details. Never hallucinate, invent or substitute a different fabric knit, weave, ribbing, sheen or surface texture than what is actually visible in the reference photos -- the rendered fabric must be recognizably the exact same physical material shown there, not a generic or plausible-looking substitute. No unintended color drift, blotching, flicker or discoloration. Match the color saturation and vibrancy of the reference photos exactly -- never render the garment flatter, greyer, duller or less saturated than it appears there, even against the darker studio backdrop; the fabric's true color intensity must read the same as in the references. Preserve all intentional washes, gradients, fading, distressing, melange effects and color variation exactly as shown in the references. Any brand tags, labels or logos visible in the references -- however small -- must be reproduced with their printed mark or graphic intact, legible and at the same relative size and position; never render a logo tag as a blank, empty or plain-colored patch. Match the same number of tags/marks as the references, never duplicated. For any printed or textured pattern (e.g. animal print, camo, stripes, florals, marbling), take the pattern's exact scale, shape, spacing and colors directly from the reference photos -- never substitute a different, generic, smoothed-over or invented pattern.",
 "primary_product": "lower garment — always the dominant commercial focus, and the ONLY product this template defines (image1-image4). The full outfit shown is not the product: the upper garment/shoes are a separately-sold Smilodox product, present only as styling context (a different video job if it needs its own accurate treatment). It should still look natural and consistent; if its own logo is already clearly legible in the references, keep it that way, but never infer, copy or invent branding for it from the lower garment, and never treat the full outfit as one branded unit."
 },
 "brand_identity": {
 "default_style": "The brand's icon, when present, is a minimal angular feline head in left-facing profile (sharp straight edges, no curves, no mouth or fang; an angular ear-spike on top; a twin-stroke swept-back mane tapering to points on the right). The wordmark, when present, is \"SMILODOX\" in bold, condensed, all-caps geometric sans-serif. CRITICAL: a single product carries EITHER the icon OR the wordmark, NEVER both together -- match whichever this product's own image1-image4 actually show (icon-only, text-only, or no branding at all); never invent the other one or add either that isn't literally visible here.",
 "no_invention_rule": "If no brand tag, label or logo graphic is visible anywhere in image1-image4, do not add one — some garments carry no visible branding at all. Different products in this same brand legitimately carry different mark styles (icon+tag vs. plain text vs. none) -- never copy the mark style from a different, previously-seen product onto this one."
 },
 "camera_and_environment": {
 "camera": "camera remains completely locked within each shot, with no zoom, pan, tilt, dolly, tracking, shake or drift; camera position, lens and framing may differ only between shots as explicitly defined",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting across all shots",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout all 4 shots -- her face (bone structure, eyes, nose, mouth, skin tone) must exactly match the real person shown in the reference photos; never generate a different-looking, generic or stylized face, and never let facial identity drift between shots",
 "skin_texture": "real human skin, not airbrushed or beautified -- visible natural micro-texture (fine pores, subtle unevenness in tone, natural sheen that varies with light and movement, faint natural blemishes or texture where the reference photos show them). Skin should look photographed, not digitally smoothed, painted, waxy or plastic; avoid a uniform matte or porcelain surface.",
 "expression": "relaxed, confident, subtle natural smile; direct eye contact in front-facing shots; in profile shots the head and gaze remain naturally aligned with the body orientation; calm, natural blink rate with eyes mostly open and steady -- no rapid, repeated or fluttering blinking; eyes look natural, alive and light-reflective, with normal moisture and catchlights -- never glassy, doll-like, dead-eyed, cross-eyed or artificial-looking",
 "feet_rule": "feet remain naturally grounded and stable; a repositioning foot may lift minimally in a biomechanically natural step before planting fully — no tiptoes, floating feet or sustained heel lifting",
 "movement_rule": "only the choreography defined per shot — no improvised movement"
 },
 "aesthetic_direction": "Premium minimalist PDP fashion aesthetic with subtle editorial polish, consistent with a single cohesive brand shoot. Fabric drapes naturally and moves with the body, emphasizing premium tactile material quality and fit. Same posture energy and framing logic across all generations.",
 "consistency_control": {
 "tolerance": "Generations across different products should look like they belong to the same campaign/shoot — same energy, same framing logic, same pacing. They do not need to be pixel-identical.",
 "fixed_across_generations": ["camera framing per shot", "choreography timing", "lighting setup", "background", "pose sequence logic"],
 "allowed_to_vary_naturally": ["exact micro-timing of fabric movement", "minor natural body motion", "product-specific garment appearance from references"],
 "seed_instruction": "Reuse the same seed value across all product generations if Higgsfield supports seed input, to minimize unwanted variance in pose, framing or lighting interpretation."
 },
 "choreography_discipline": "Timing windows below (e.g. 0.0-0.5s) are fixed and repeat consistently across generations; only the fabric's visual texture may vary. WITHIN a single shot, motion flows continuously through that shot's own windows -- no speeding into a pose then freezing at a window boundary. This applies ONLY inside each shot, NOT between shots: every cut to the next shot is still a hard cut to that shot's own camera view (per the shot list below), never a continuation of the previous shot's move, and the model does not visibly rotate or reposition across the cut. Exception: shot_04_garment_detail is a deliberate total static hold (per its own choreography below) -- follow that instruction instead.",
 "shots": [
 {
 "id": "shot_01_front_full_body",
 "primary_product_reference": "image1",
 "supporting_reference_roles": ["image2 for lower-garment material and front detail", "image3 for construction continuity"],
 "view": "direct front, full body, both shoes visible, model centered",
 "framing": "maximize lower-garment visibility while maintaining comfortable, consistent small headroom and full shoe visibility; the complete garment from waistband to hem remains unobstructed and commercially prominent",
 "choreography": {
 "0.0-0.5s": "weight shifts naturally from left to right leg",
 "0.5-1.0s": "right leg becomes primary support, left knee soft and relaxed",
 "1.0-1.5s": "left foot repositions slightly outward and forward with a minimal natural step, then plants fully and remains stable",
 "1.5-2.5s": "settles into relaxed asymmetric stance, holds pose, subtle smile, direct eye contact"
 }
 },
 {
 "id": "shot_02_side_lower_garment",
 "primary_product_reference": "image2",
 "supporting_reference_roles": ["image1 for model identity, proportions, overall garment silhouette and color", "image3 for construction continuity where relevant"],
 "view": "exact 90-degree left side profile, lower garment dominates composition -- a closer, garment-focused crop than shot 1's full-body framing, not a repeat of it; head and gaze follow the profile orientation if visible",
 "framing": "product-centered crop that keeps the entire lower garment from waistband to hem fully visible; include sufficient upper-body and footwear context without reducing the garment's commercial prominence, adapting the crop to the product length",
 "choreography": {
 "0.0-0.5s": "weight shifts naturally from left to right leg",
 "0.5-1.0s": "right leg becomes primary support, knees remain relaxed",
 "1.0-1.5s": "subtle natural weight transfer with minimal torso response; waistband, rise and fit remain stable and clearly readable",
 "1.5-2.5s": "settles into final side-profile stance and holds pose with gaze aligned to the body if visible"
 }
 },
 {
 "id": "shot_03_back_lower_garment",
 "primary_product_reference": "image3",
 "supporting_reference_roles": ["image1 for model identity, proportions and overall color", "image2 for fabric and construction continuity"],
 "view": "exact 180-degree rear view, lower garment dominates composition -- a closer, garment-focused crop than shot 1's full-body framing, not a repeat of it",
 "framing": "product-centered crop that keeps the entire lower garment from waistband to hem fully visible; include sufficient upper-body and footwear context without reducing the garment's commercial prominence, with the model centered and crop adapted to product length",
 "choreography": {
 "0.0-0.5s": "weight shifts naturally from right to left leg",
 "0.5-1.0s": "left leg becomes primary support, right knee soft and relaxed",
 "1.0-1.5s": "right foot repositions slightly outward and back with a minimal natural step, then plants fully and remains stable",
 "1.5-2.5s": "settles into final rear stance and holds pose"
 }
 },
 {
 "id": "shot_04_garment_detail",
 "primary_product_reference": "image4",
 "supporting_reference_roles": ["image2 for material and texture continuity", "image1 and image3 for overall product identity"],
 "view": "tight locked-off close-up matching the exact detail shown in image4 — no body or camera movement, only extremely subtle fabric response",
 "framing": "composition matches image4 as closely as possible, with maximum sharpness on the exact product detail",
 "choreography": {
 "0.0-2.5s": "static hold, maximum sharpness on the exact garment detail"
 }
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking", "camera shake", "camera drift",
 "tiptoes", "sustained heel lifting", "floating feet", "foot sliding", "foot-ground penetration",
 "garment redesign", "garment morphing", "frame-to-frame garment morphing", "color drift", "logo drift", "blank logo tag", "missing logo graphic", "illegible logo", "invented print pattern", "altered print pattern", "generic pattern substitution", "invented details",
 "fabric hallucination", "invented fabric texture", "generic fabric substitution", "changed fabric knit or weave", "wrong fabric sheen",
 "different face", "generic face", "stylized face", "face identity drift", "face swap", "altered facial features", "different model",
 "desaturated colors", "muted colors", "washed-out color", "flattened color contrast", "dull or lifeless garment color",
 "jerky movement", "sudden pose snap", "abrupt motion", "staccato motion", "freeze-frame pause between movements", "hectic movement", "rushed weight shift",
 "model turning between shots", "body rotation carried across a cut", "continuous camera move across a cut", "full body framing in a product close-up shot",
 "invented logo icon", "added brand icon not shown in references", "invented tag graphic", "generic default logo substituted for actual mark", "logo style copied from a different product", "icon and wordmark combined on one garment", "curved or rounded logo icon shape", "roaring open-mouth logo face", "outfit treated as a single product", "branding copied across the full outfit", "duplicate logo tag", "extra brand tag not in references",
 "unintended fabric blotches or discoloration", "temporal texture instability", "fabric texture crawling", "unnatural fabric physics", "seam flicker", "hardware flicker",
 "motion blur on garment", "pixelation", "compression artifacts", "loss of product detail",
 "walking", "turning", "spinning", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion", "malformed hands", "extra or fused fingers", "artifacts where hands touch fabric or skin", "excessive blinking", "rapid eye blinking", "eye flutter", "glassy eyes", "doll-like eyes", "dead-eyed stare", "artificial eye look",
 "background morphing", "warped straight seams", "lens flare", "film grain", "vignette", "depth of field blur",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter", "airbrushed skin", "over-smoothed skin", "plastic skin", "waxy skin", "porcelain skin", "digitally painted skin", "uncanny smooth complexion",
 "non-adult appearance", "unintended skin exposure beyond garment design", "combat implements", "physical altercation",
 "discriminatory symbols", "religious imagery", "substance use", "hateful imagery"
 ]
}"""

# Kling 3.0 only exposes start_image/end_image (2 reference slots) -- not the
# 4-image array the main templates above assume. These two variants keep the same
# shot-based structure, focus-on-garment intent AND hard-cuts editing style as the
# originals (Zalando PDP acceptance requires the same cut style across the whole
# campaign), just with 3 shots instead of 4 -- no dedicated detail shot, since
# there is no 4th reference image to ground it: full body -> hard cut to a static
# close-up on the SAME front reference (no new image, just a tighter static crop,
# no camera movement) -> hard cut to the back reference. ~3.33s per shot (10s / 3).
# Revised 2026-08-21 alongside OBERTEIL/UNTERTEIL_PROMPT: same feet_rule fix, same
# clarified camera rule, same color-preservation wording in product_lock, and the
# same expanded negative_prompt list, for full quality parity across all 4 prompts.
KLING_OBERTEIL_PROMPT = r"""{
 "campaign": "zalando_upper_garment_video_kling",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando guidance recommends approximately 15 seconds, with 12-18 seconds stated as the preferred editing range. This campaign intentionally uses the 10-second format set below.",
 "content_restrictions": "adult model only, shown fully dressed in the reference garments at all times with no additional skin exposure beyond the garments' own design; no combat implements or physical altercation of any kind; no discriminatory, political or religious content; no substance use; no on-screen text or sound"
 },
 "video_spec": {
 "aspect_ratio": "9:16",
 "resolution_min": "762x1100",
 "fps": 24,
 "duration_seconds": 10,
 "shot_count": 1,
 "editing": "one single continuous shot for the full 10 seconds -- no cuts, no transitions, no camera movement of any kind; the only motion is the model's own body turning in place",
 "audio_text_graphics": "none"
 },
 "reference_images": {
 "start_image": "full body, front view — defines silhouette, proportions, overall color, model appearance, upper garment",
 "end_image": "full body, back view — defines rear construction, rear print/label, upper garment"
 },
 "product_lock": {
 "rule": "The start and end reference show the SAME physical upper garment on the SAME model. Match color, cut, fabric, texture, print, logo and construction exactly to both references throughout the shot -- never invent new detail that isn't visible in start_image/end_image. Never hallucinate, invent or substitute a different fabric knit, weave, ribbing, sheen or surface texture than what is actually visible in start_image/end_image -- the rendered fabric must be recognizably the exact same physical material shown there, not a generic or plausible-looking substitute. No unintended color drift, blotching, flicker or discoloration. Match the color saturation and vibrancy of the reference photos exactly -- never render the garment flatter, greyer, duller or less saturated than it appears there, even against the darker studio backdrop; the fabric's true color intensity must read the same as in the references. Preserve all intentional washes, gradients, fading, distressing, melange effects and color variation exactly as shown in the references. Any brand tags, labels or logos visible in the references -- however small -- must be reproduced with their printed mark or graphic intact, legible and at the same relative size and position; never render a logo tag as a blank, empty or plain-colored patch. Match the same number of tags/marks as the references, never duplicated. For any printed or textured pattern (e.g. animal print, camo, stripes, florals, marbling), take the pattern's exact scale, shape, spacing and colors directly from the reference photos -- never substitute a different, generic, smoothed-over or invented pattern.",
 "primary_product": "upper garment — always the dominant commercial focus, and the ONLY product this template defines (start_image/end_image). The full outfit shown is not the product: the lower garment/shoes are a separately-sold Smilodox product, present only as styling context (a different video job if it needs its own accurate treatment). It should still look natural and consistent; if its own logo is already clearly legible in the references, keep it that way, but never infer, copy or invent branding for it from the upper garment, and never treat the full outfit as one branded unit."
 },
 "brand_identity": {
 "logo_icon": "the brand's logo icon is a minimal angular feline head silhouette in left-facing profile -- sharp straight polygon edges only, no curves, no open mouth or fang. A sharp upward angular spike (alert ear) tops the head; snout comes to a point. Behind it, two parallel swept-back strokes of different lengths taper to points on the right (twin speed-streaks, not one curved line). Flat solid black, no gradients, on a plain white background.",
 "wordmark": "the brand name \"SMILODOX\" in bold, black, heavy, condensed, all-caps geometric sans-serif lettering with straight-edged blocky letterforms and no serifs",
 "application_on_garment": "How branding appears varies by product -- the icon/wordmark descriptions above are ground truth for the graphics themselves, not a requirement to use both. Some products carry it as a small tag (icon-only or wordmark-only); others have only \"SMILODOX\" woven/printed into the fabric, no icon. CRITICAL: a single product carries EITHER the icon OR the wordmark, NEVER both together -- match whichever start_image/end_image actually show, and never copy the mark style from a different product onto this one. Reproduce it at the natural size and distance it appears in the reference photos -- never zoom or crop in specifically to feature it; if it is small in the references, it stays small here too."
 },
 "camera_and_environment": {
 "camera": "camera remains completely locked for the entire 10-second shot -- no zoom, pan, tilt, dolly, tracking, shake or drift, and no cuts. Camera position, distance and framing never change; the model's own body turn is the only motion",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting throughout",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout the shot -- her face (bone structure, eyes, nose, mouth, skin tone) must exactly match the real person shown in the reference photos; never generate a different-looking, generic or stylized face, and never let facial identity drift over the course of the turn",
 "skin_texture": "real human skin, not airbrushed or beautified -- visible natural micro-texture (fine pores, subtle unevenness in tone, natural sheen that varies with light and movement, faint natural blemishes or texture where the reference photos show them). Skin should look photographed, not digitally smoothed, painted, waxy or plastic; avoid a uniform matte or porcelain surface.",
 "expression": "relaxed, confident, subtle natural smile, direct eye contact when facing camera; calm, natural blink rate with eyes mostly open and steady -- no rapid, repeated or fluttering blinking; eyes look natural, alive and light-reflective, with normal moisture and catchlights -- never glassy, doll-like, dead-eyed, cross-eyed or artificial-looking",
 "feet_rule": "feet remain naturally grounded and stable throughout the turn; weight shifts smoothly between feet as the body rotates -- no tiptoes, floating feet, sustained heel lifting or foot sliding",
 "movement_rule": "only the single continuous turn defined below — no improvised movement, no walking, no steps away from center"
 },
 "aesthetic_direction": "Premium minimalist PDP fashion aesthetic with subtle editorial polish. Fabric drapes softly and catches light naturally, emphasizing premium tactile material quality as the body turns.",
 "consistency_control": {
 "tolerance": "Generations across different products should look like they belong to the same campaign/shoot — same energy, same framing, same pacing of the turn. They do not need to be pixel-identical.",
 "fixed_across_generations": ["camera framing (locked, unchanged for the full 10s)", "turn direction and timing", "lighting setup", "background"],
 "allowed_to_vary_naturally": ["exact micro-timing of fabric movement", "minor natural body motion", "product-specific garment appearance from references"],
 "seed_instruction": "Reuse the same seed value across all product generations if Higgsfield supports seed input, to minimize unwanted variance in pose, framing or lighting interpretation."
 },
 "choreography_discipline": "This is ONE single continuous 10-second shot -- there are no cuts and no separate shots. Motion must flow smoothly and continuously through the entire duration, in the pacing defined below; the timing windows mark one continuous physical motion path, not discrete keyframes. Never speed up into a pose and then freeze/pause, never a sudden snap -- only gradual, evenly-paced continuous turning motion throughout.",
 "shots": [
 {
 "id": "shot_01_360_turn",
 "duration_seconds": 10,
 "view": "single continuous shot, full body always in frame, camera completely locked -- the model smoothly and continuously turns her own body in place, starting facing front exactly as start_image shows, rotating through a natural side profile, ending facing away exactly as end_image shows. One fluid, continuous rotation, never a series of cuts or poses, and never a close-up or zoom at any point",
 "framing": "full body always visible including both shoes, consistent headroom the entire 10 seconds -- the same single unchanging framing throughout; only the model's body orientation changes, the camera never moves closer or further",
 "choreography": {
 "0.0-1.5s": "settles into a relaxed front-facing stance matching start_image exactly, subtle natural weight sway, direct eye contact",
 "1.5-8.0s": "smooth, continuous, evenly-paced rotation of the whole body in place, weight shifting naturally with the turn, passing through a natural side profile around the midpoint -- one fluid motion, never a snap, never a pause",
 "8.0-10.0s": "settles into a relaxed rear-facing stance matching end_image exactly, subtle natural weight sway"
 }
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking", "camera shake", "camera drift", "any cut or scene change", "close-up crop", "unmotivated zoom on logo or fabric", "camera framing change mid-shot",
 "tiptoes", "sustained heel lifting", "floating feet", "foot sliding", "foot-ground penetration",
 "garment redesign", "garment morphing", "frame-to-frame garment morphing", "color drift", "logo drift", "blank logo tag", "missing logo graphic", "illegible logo", "invented print pattern", "altered print pattern", "generic pattern substitution", "invented details",
 "fabric hallucination", "invented fabric texture", "generic fabric substitution", "changed fabric knit or weave", "wrong fabric sheen",
 "different face", "generic face", "stylized face", "face identity drift", "face swap", "altered facial features", "different model",
 "desaturated colors", "muted colors", "washed-out color", "flattened color contrast", "dull or lifeless garment color",
 "jerky movement", "sudden pose snap", "abrupt motion", "staccato motion", "freeze-frame pause mid-turn", "hectic movement", "rushed weight shift",
 "invented logo icon", "added brand icon not shown in references", "invented tag graphic", "generic default logo substituted for actual mark", "logo style copied from a different product", "icon and wordmark combined on one garment", "curved or rounded logo icon shape", "roaring open-mouth logo face", "outfit treated as a single product", "branding copied across the full outfit", "duplicate logo tag", "extra brand tag not in references",
 "unintended fabric blotches or discoloration", "temporal texture instability", "fabric texture crawling", "unnatural fabric physics", "seam flicker", "hardware flicker",
 "motion blur on garment", "pixelation", "compression artifacts", "loss of product detail",
 "walking", "spinning too fast", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion", "malformed hands", "extra or fused fingers", "artifacts where hands touch fabric or skin", "excessive blinking", "rapid eye blinking", "eye flutter", "glassy eyes", "doll-like eyes", "dead-eyed stare", "artificial eye look",
 "background morphing", "warped straight seams", "lens flare", "film grain", "vignette", "depth of field blur",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter", "airbrushed skin", "over-smoothed skin", "plastic skin", "waxy skin", "porcelain skin", "digitally painted skin", "uncanny smooth complexion",
 "non-adult appearance", "unintended skin exposure beyond garment design", "combat implements", "physical altercation",
 "discriminatory symbols", "religious imagery", "substance use", "hateful imagery"
 ]
}"""

KLING_UNTERTEIL_PROMPT = r"""{
 "campaign": "zalando_lower_garment_video_kling",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando guidance recommends approximately 15 seconds, with 12-18 seconds stated as the preferred editing range. This campaign intentionally uses the 10-second format set below.",
 "content_restrictions": "adult model only, shown fully dressed in the reference garments at all times with no additional skin exposure beyond the garments' own design; no combat implements or physical altercation of any kind; no discriminatory, political or religious content; no substance use; no on-screen text or sound"
 },
 "video_spec": {
 "aspect_ratio": "9:16",
 "resolution_min": "762x1100",
 "fps": 24,
 "duration_seconds": 10,
 "shot_count": 1,
 "editing": "one single continuous shot for the full 10 seconds -- no cuts, no transitions, no camera movement of any kind; the only motion is the model's own body turning in place",
 "audio_text_graphics": "none"
 },
 "reference_images": {
 "start_image": "full body, front view — defines silhouette, proportions, overall color, model appearance, lower garment",
 "end_image": "full body, back view — defines rear construction, rear pockets, back print/label, lower garment"
 },
 "product_lock": {
 "rule": "The start and end reference show the SAME physical lower garment on the SAME model. Match color, cut, fabric, texture, print, logo, waistband, pockets and construction exactly to both references throughout the shot -- never invent new detail that isn't visible in start_image/end_image. Never hallucinate, invent or substitute a different fabric knit, weave, ribbing, sheen or surface texture than what is actually visible in start_image/end_image -- the rendered fabric must be recognizably the exact same physical material shown there, not a generic or plausible-looking substitute. No unintended color drift, blotching, flicker or discoloration. Match the color saturation and vibrancy of the reference photos exactly -- never render the garment flatter, greyer, duller or less saturated than it appears there, even against the darker studio backdrop; the fabric's true color intensity must read the same as in the references. Preserve all intentional washes, gradients, fading, distressing, melange effects and color variation exactly as shown in the references. Any brand tags, labels or logos visible in the references -- however small -- must be reproduced with their printed mark or graphic intact, legible and at the same relative size and position; never render a logo tag as a blank, empty or plain-colored patch. Match the same number of tags/marks as the references, never duplicated. For any printed or textured pattern (e.g. animal print, camo, stripes, florals, marbling), take the pattern's exact scale, shape, spacing and colors directly from the reference photos -- never substitute a different, generic, smoothed-over or invented pattern.",
 "primary_product": "lower garment — always the dominant commercial focus, and the ONLY product this template defines (start_image/end_image). The full outfit shown is not the product: the upper garment/shoes are a separately-sold Smilodox product, present only as styling context (a different video job if it needs its own accurate treatment). It should still look natural and consistent; if its own logo is already clearly legible in the references, keep it that way, but never infer, copy or invent branding for it from the lower garment, and never treat the full outfit as one branded unit."
 },
 "brand_identity": {
 "logo_icon": "the brand's logo icon is a minimal angular feline head silhouette in left-facing profile -- sharp straight polygon edges only, no curves, no open mouth or fang. A sharp upward angular spike (alert ear) tops the head; snout comes to a point. Behind it, two parallel swept-back strokes of different lengths taper to points on the right (twin speed-streaks, not one curved line). Flat solid black, no gradients, on a plain white background.",
 "wordmark": "the brand name \"SMILODOX\" in bold, black, heavy, condensed, all-caps geometric sans-serif lettering with straight-edged blocky letterforms and no serifs",
 "application_on_garment": "How branding appears varies by product -- the icon/wordmark descriptions above are ground truth for the graphics themselves, not a requirement to use both. Some products carry it as a small tag (icon-only or wordmark-only); others have only \"SMILODOX\" woven/printed into the fabric, no icon. CRITICAL: a single product carries EITHER the icon OR the wordmark, NEVER both together -- match whichever start_image/end_image actually show, and never copy the mark style from a different product onto this one. Reproduce it at the natural size and distance it appears in the reference photos -- never zoom or crop in specifically to feature it; if it is small in the references, it stays small here too."
 },
 "camera_and_environment": {
 "camera": "camera remains completely locked for the entire 10-second shot -- no zoom, pan, tilt, dolly, tracking, shake or drift, and no cuts. Camera position, distance and framing never change; the model's own body turn is the only motion",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting throughout",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout the shot -- her face (bone structure, eyes, nose, mouth, skin tone) must exactly match the real person shown in the reference photos; never generate a different-looking, generic or stylized face, and never let facial identity drift over the course of the turn",
 "skin_texture": "real human skin, not airbrushed or beautified -- visible natural micro-texture (fine pores, subtle unevenness in tone, natural sheen that varies with light and movement, faint natural blemishes or texture where the reference photos show them). Skin should look photographed, not digitally smoothed, painted, waxy or plastic; avoid a uniform matte or porcelain surface.",
 "expression": "relaxed, confident, subtle natural smile, direct eye contact when facing camera; calm, natural blink rate with eyes mostly open and steady -- no rapid, repeated or fluttering blinking; eyes look natural, alive and light-reflective, with normal moisture and catchlights -- never glassy, doll-like, dead-eyed, cross-eyed or artificial-looking",
 "feet_rule": "feet remain naturally grounded and stable throughout the turn; weight shifts smoothly between feet as the body rotates -- no tiptoes, floating feet, sustained heel lifting or foot sliding",
 "movement_rule": "only the single continuous turn defined below — no improvised movement, no walking, no steps away from center"
 },
 "aesthetic_direction": "Premium minimalist PDP fashion aesthetic with subtle editorial polish. Fabric drapes naturally and moves with the body, emphasizing premium tactile material quality and fit as the body turns.",
 "consistency_control": {
 "tolerance": "Generations across different products should look like they belong to the same campaign/shoot — same energy, same framing, same pacing of the turn. They do not need to be pixel-identical.",
 "fixed_across_generations": ["camera framing (locked, unchanged for the full 10s)", "turn direction and timing", "lighting setup", "background"],
 "allowed_to_vary_naturally": ["exact micro-timing of fabric movement", "minor natural body motion", "product-specific garment appearance from references"],
 "seed_instruction": "Reuse the same seed value across all product generations if Higgsfield supports seed input, to minimize unwanted variance in pose, framing or lighting interpretation."
 },
 "choreography_discipline": "This is ONE single continuous 10-second shot -- there are no cuts and no separate shots. Motion must flow smoothly and continuously through the entire duration, in the pacing defined below; the timing windows mark one continuous physical motion path, not discrete keyframes. Never speed up into a pose and then freeze/pause, never a sudden snap -- only gradual, evenly-paced continuous turning motion throughout.",
 "shots": [
 {
 "id": "shot_01_360_turn",
 "duration_seconds": 10,
 "view": "single continuous shot, full body always in frame, camera completely locked -- the model smoothly and continuously turns her own body in place, starting facing front exactly as start_image shows, rotating through a natural side profile, ending facing away exactly as end_image shows. One fluid, continuous rotation, never a series of cuts or poses, and never a close-up or zoom at any point",
 "framing": "full body always visible including both shoes, consistent headroom the entire 10 seconds -- the same single unchanging framing throughout; only the model's body orientation changes, the camera never moves closer or further",
 "choreography": {
 "0.0-1.5s": "settles into a relaxed front-facing stance matching start_image exactly, subtle natural weight sway, direct eye contact",
 "1.5-8.0s": "smooth, continuous, evenly-paced rotation of the whole body in place, weight shifting naturally with the turn, passing through a natural side profile around the midpoint -- one fluid motion, never a snap, never a pause",
 "8.0-10.0s": "settles into a relaxed rear-facing stance matching end_image exactly, subtle natural weight sway"
 }
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking", "camera shake", "camera drift", "any cut or scene change", "close-up crop", "unmotivated zoom on logo or fabric", "camera framing change mid-shot",
 "tiptoes", "sustained heel lifting", "floating feet", "foot sliding", "foot-ground penetration",
 "garment redesign", "garment morphing", "frame-to-frame garment morphing", "color drift", "logo drift", "blank logo tag", "missing logo graphic", "illegible logo", "invented print pattern", "altered print pattern", "generic pattern substitution", "invented details",
 "fabric hallucination", "invented fabric texture", "generic fabric substitution", "changed fabric knit or weave", "wrong fabric sheen",
 "different face", "generic face", "stylized face", "face identity drift", "face swap", "altered facial features", "different model",
 "desaturated colors", "muted colors", "washed-out color", "flattened color contrast", "dull or lifeless garment color",
 "jerky movement", "sudden pose snap", "abrupt motion", "staccato motion", "freeze-frame pause mid-turn", "hectic movement", "rushed weight shift",
 "invented logo icon", "added brand icon not shown in references", "invented tag graphic", "generic default logo substituted for actual mark", "logo style copied from a different product", "icon and wordmark combined on one garment", "curved or rounded logo icon shape", "roaring open-mouth logo face", "outfit treated as a single product", "branding copied across the full outfit", "duplicate logo tag", "extra brand tag not in references",
 "unintended fabric blotches or discoloration", "temporal texture instability", "fabric texture crawling", "unnatural fabric physics", "seam flicker", "hardware flicker",
 "motion blur on garment", "pixelation", "compression artifacts", "loss of product detail",
 "walking", "spinning too fast", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion", "malformed hands", "extra or fused fingers", "artifacts where hands touch fabric or skin", "excessive blinking", "rapid eye blinking", "eye flutter", "glassy eyes", "doll-like eyes", "dead-eyed stare", "artificial eye look",
 "background morphing", "warped straight seams", "lens flare", "film grain", "vignette", "depth of field blur",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter", "airbrushed skin", "over-smoothed skin", "plastic skin", "waxy skin", "porcelain skin", "digitally painted skin", "uncanny smooth complexion",
 "non-adult appearance", "unintended skin exposure beyond garment design", "combat implements", "physical altercation",
 "discriminatory symbols", "religious imagery", "substance use", "hateful imagery"
 ]
}"""

# Models limited to a 2-image start/end pair instead of the full 4-image array use
# this prompt variant, keyed by garment template_key, instead of TEMPLATES[key]["prompt_text"].
TWO_IMAGE_PROMPT_OVERRIDES = {
    "kling3_0": {
        "oberteil": KLING_OBERTEIL_PROMPT,
        "unterteil": KLING_UNTERTEIL_PROMPT,
    },
}


def resolve_prompt_text(template_key: str, model: str) -> str:
    override = TWO_IMAGE_PROMPT_OVERRIDES.get(model, {}).get(template_key)
    if override:
        return override
    return TEMPLATES[template_key]["prompt_text"]


TEMPLATES = {
    "oberteil": {
        "garment_type": "Oberteil",
        "prompt_text": OBERTEIL_PROMPT,
        "duration": 10.0,
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "shot_count": 4,
    },
    "unterteil": {
        "garment_type": "Unterteil",
        "prompt_text": UNTERTEIL_PROMPT,
        "duration": 10.0,
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "shot_count": 4,
    },
}


def seed_templates():
    from datetime import datetime, timezone
    from . import db

    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    with db.get_conn() as conn:
        for key, t in TEMPLATES.items():
            conn.execute(
                """
                INSERT INTO prompt_templates (
                    template_key, garment_type, prompt_text, duration, aspect_ratio, resolution, shot_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(template_key) DO UPDATE SET
                    garment_type=excluded.garment_type,
                    prompt_text=excluded.prompt_text,
                    duration=excluded.duration,
                    aspect_ratio=excluded.aspect_ratio,
                    resolution=excluded.resolution,
                    shot_count=excluded.shot_count,
                    updated_at=excluded.updated_at
                """,
                (key, t["garment_type"], t["prompt_text"], t["duration"], t["aspect_ratio"], t["resolution"], t["shot_count"], now, now),
            )
