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
 "duration_note": "Zalando recommends ~15s (comfort range 12-18s) as guidance, not a hard requirement -- this campaign intentionally keeps the shorter duration set below",
 "content_restrictions": "no minors/children anywhere in frame, no nudity or exposed intimate areas, no violence or weapons, no discriminatory/political/religious content, no substance use, no on-screen text or sound"
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
 "image1": "full body, front view — defines silhouette, proportions, overall color, model appearance",
 "image2": "close-up of upper garment — defines fabric, texture, neckline, sleeves, seams, print, logo",
 "image3": "back view — defines rear construction, rear print/label",
 "image4": "product detail shot — defines exact stitching/hardware/print detail for final shot"
 },
 "product_lock": {
 "rule": "All 4 images show the SAME physical upper garment. Match color, cut, fabric, texture, print, logo and construction exactly to the references in every shot. Never redesign, simplify or invent details. Fabric coloring stays perfectly even, no blotches or discoloration.",
 "primary_product": "upper garment — always the dominant commercial focus. Lower garments/shoes are styling context only."
 },
 "camera_and_environment": {
 "camera": "fixed studio position, no zoom/pan/tilt/dolly/tracking in any shot",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting across all shots",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout all 4 shots",
 "expression": "relaxed, confident, subtle natural smile, direct eye contact when face is visible",
 "feet_rule": "both feet fully flat on the ground at all times — no tiptoes, no heel lifting",
 "movement_rule": "only the choreography defined per shot — no improvised movement"
 },
 "aesthetic_direction": "Elevated editorial e-commerce fashion mood, consistent with a single cohesive brand shoot. Fabric drapes softly and catches light naturally, emphasizing premium tactile material quality. Same posture energy and framing logic across all generations",
 "consistency_control": {
 "tolerance": "Generations across different products should look like they belong to the same campaign/shoot — same energy, same framing logic, same pacing. They do not need to be pixel-identical.",
 "fixed_across_generations": ["camera framing per shot", "choreography timing", "lighting setup", "background", "pose sequence logic"],
 "allowed_to_vary_naturally": ["exact micro-timing of fabric movement", "minor natural body motion", "product-specific garment appearance from references"],
 "seed_instruction": "Reuse the same seed value across all product generations if Higgsfield supports seed input, to minimize unwanted variance in pose, framing or lighting interpretation."
 },
 "choreography_discipline": "Timing windows below (e.g. 0.0-0.5s) are fixed and must repeat identically across every generation. Only the visual texture of the movement — how the fabric responds — may vary slightly.",
 "shots": [
 {
 "id": "shot_01_front_full_body",
 "reference": "image1",
 "view": "direct front, full body, both shoes visible, model centered",
 "framing": "headroom fixed: crown of head to top of frame = one head-height, consistent across all generations",
 "choreography": {
 "0.0-0.5s": "weight shifts noticeably from left to right leg",
 "0.5-1.0s": "right leg becomes primary support, left knee soft and relaxed",
 "1.0-1.5s": "left foot slides slightly outward and forward, both feet stay flat",
 "1.5-2.5s": "settles into relaxed asymmetric stance, holds pose, subtle smile, direct eye contact"
 }
 },
 {
 "id": "shot_02_side_upper_garment",
 "reference": "image2",
 "view": "exact 90-degree left side profile, upper garment dominates composition",
 "framing": "frame bottom edge at mid-thigh, head fully visible, consistent across all generations of this shot type",
 "choreography": {
 "0.0-0.5s": "weight shifts from left to right leg",
 "0.5-1.0s": "right leg becomes primary support",
 "1.0-1.5s": "subtle forward-and-back pelvis translation, no rotation",
 "1.5-2.5s": "settles into final side-profile stance, holds pose"
 }
 },
 {
 "id": "shot_03_back_upper_garment",
 "reference": "image3",
 "view": "exact 180-degree rear view, upper garment dominates composition",
 "framing": "frame bottom edge at mid-thigh, head fully visible, model perfectly centered, consistent across all generations of this shot type",
 "choreography": {
 "0.0-0.5s": "weight shifts from right to left leg",
 "0.5-1.0s": "left leg becomes primary support",
 "1.0-1.5s": "right foot slides slightly outward and back, stays flat",
 "1.5-2.5s": "settles into final rear stance, holds pose"
 }
 },
 {
 "id": "shot_04_garment_detail",
 "reference": "image4",
 "view": "tight locked-off close-up matching the exact detail shown in image4 — no body or camera movement, only extremely subtle fabric response",
 "framing": "composition matches image4 as closely as possible, maximum sharpness on the exact detail",
 "choreography": {
 "0.0-2.5s": "static hold, maximum sharpness on the exact garment detail"
 }
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking",
 "tiptoes", "heel lifting", "floating feet",
 "garment redesign", "color drift", "logo drift", "invented details",
 "fabric blotches or discoloration",
 "walking", "turning", "spinning", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter",
 "children", "minors", "nudity", "exposed intimate areas", "weapons", "violence",
 "political symbols", "religious imagery", "drug use", "hate symbols"
 ]
}"""

# Restructured 2026-08-20 to mirror OBERTEIL_PROMPT's schema/timing/tone -- see module docstring.
UNTERTEIL_PROMPT = r"""{
 "campaign": "zalando_lower_garment_video",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando recommends ~15s (comfort range 12-18s) as guidance, not a hard requirement -- this campaign intentionally keeps the shorter duration set below",
 "content_restrictions": "no minors/children anywhere in frame, no nudity or exposed intimate areas, no violence or weapons, no discriminatory/political/religious content, no substance use, no on-screen text or sound"
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
 "image1": "full body, front view — defines silhouette, proportions, overall color, model appearance",
 "image2": "close-up of lower garment — defines fabric, texture, waistband, pockets, seams, print, hardware",
 "image3": "back view — defines rear construction, rear pockets, back print/label",
 "image4": "product detail shot — defines exact stitching/hardware/print detail for final shot"
 },
 "product_lock": {
 "rule": "All 4 images show the SAME physical lower garment. Match color, cut, fabric, texture, print, logo, waistband, pockets and construction exactly to the references in every shot. Never redesign, simplify or invent details. Fabric coloring stays perfectly even, no blotches or discoloration.",
 "primary_product": "lower garment — always the dominant commercial focus. Upper garments/shoes are styling context only."
 },
 "camera_and_environment": {
 "camera": "fixed studio position, no zoom/pan/tilt/dolly/tracking in any shot",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting across all shots",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout all 4 shots",
 "expression": "relaxed, confident, subtle natural smile, direct eye contact when face is visible",
 "feet_rule": "both feet fully flat on the ground at all times — no tiptoes, no heel lifting",
 "movement_rule": "only the choreography defined per shot — no improvised movement"
 },
 "aesthetic_direction": "Elevated editorial e-commerce fashion mood, consistent with a single cohesive brand shoot. Fabric drapes naturally and moves with the body, emphasizing premium tactile material quality and fit. Same posture energy and framing logic across all generations",
 "consistency_control": {
 "tolerance": "Generations across different products should look like they belong to the same campaign/shoot — same energy, same framing logic, same pacing. They do not need to be pixel-identical.",
 "fixed_across_generations": ["camera framing per shot", "choreography timing", "lighting setup", "background", "pose sequence logic"],
 "allowed_to_vary_naturally": ["exact micro-timing of fabric movement", "minor natural body motion", "product-specific garment appearance from references"],
 "seed_instruction": "Reuse the same seed value across all product generations if Higgsfield supports seed input, to minimize unwanted variance in pose, framing or lighting interpretation."
 },
 "choreography_discipline": "Timing windows below (e.g. 0.0-0.5s) are fixed and must repeat identically across every generation. Only the visual texture of the movement — how the fabric responds — may vary slightly.",
 "shots": [
 {
 "id": "shot_01_front_full_body",
 "reference": "image1",
 "view": "direct front, full body, both shoes visible, model centered",
 "framing": "headroom fixed: crown of head to top of frame = one head-height, consistent across all generations",
 "choreography": {
 "0.0-0.5s": "weight shifts noticeably from left to right leg",
 "0.5-1.0s": "right leg becomes primary support, left knee soft and relaxed",
 "1.0-1.5s": "left foot slides slightly outward and forward, both feet stay flat",
 "1.5-2.5s": "settles into relaxed asymmetric stance, holds pose, subtle smile, direct eye contact"
 }
 },
 {
 "id": "shot_02_side_lower_garment",
 "reference": "image2",
 "view": "exact 90-degree left side profile, lower garment dominates composition",
 "framing": "frame top edge at chest, both feet fully visible, consistent across all generations of this shot type",
 "choreography": {
 "0.0-0.5s": "weight shifts from left to right leg",
 "0.5-1.0s": "right leg becomes primary support",
 "1.0-1.5s": "subtle forward-and-back pelvis translation, no rotation",
 "1.5-2.5s": "settles into final side-profile stance, holds pose"
 }
 },
 {
 "id": "shot_03_back_lower_garment",
 "reference": "image3",
 "view": "exact 180-degree rear view, lower garment dominates composition",
 "framing": "frame top edge at chest, both feet fully visible, model perfectly centered, consistent across all generations of this shot type",
 "choreography": {
 "0.0-0.5s": "weight shifts from right to left leg",
 "0.5-1.0s": "left leg becomes primary support",
 "1.0-1.5s": "right foot slides slightly outward and back, stays flat",
 "1.5-2.5s": "settles into final rear stance, holds pose"
 }
 },
 {
 "id": "shot_04_garment_detail",
 "reference": "image4",
 "view": "tight locked-off close-up matching the exact detail shown in image4 — no body or camera movement, only extremely subtle fabric response",
 "framing": "composition matches image4 as closely as possible, maximum sharpness on the exact detail",
 "choreography": {
 "0.0-2.5s": "static hold, maximum sharpness on the exact garment detail"
 }
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking",
 "tiptoes", "heel lifting", "floating feet",
 "garment redesign", "color drift", "logo drift", "invented details",
 "fabric blotches or discoloration",
 "walking", "turning", "spinning", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter",
 "children", "minors", "nudity", "exposed intimate areas", "weapons", "violence",
 "political symbols", "religious imagery", "drug use", "hate symbols"
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
KLING_OBERTEIL_PROMPT = r"""{
 "campaign": "zalando_upper_garment_video_kling",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando recommends ~15s (comfort range 12-18s) as guidance, not a hard requirement -- this campaign intentionally keeps the shorter duration set below",
 "content_restrictions": "no minors/children anywhere in frame, no nudity or exposed intimate areas, no violence or weapons, no discriminatory/political/religious content, no substance use, no on-screen text or sound"
 },
 "video_spec": {
 "aspect_ratio": "9:16",
 "fps": 24,
 "duration_seconds": 10,
 "shot_count": 3,
 "shot_duration_seconds": 3.33,
 "editing": "hard cuts only, no transitions, no camera movement of any kind",
 "audio_text_graphics": "none"
 },
 "reference_images": {
 "start_image": "full body, front view — defines silhouette, proportions, overall color, model appearance, upper garment",
 "end_image": "full body, back view — defines rear construction, rear print/label, upper garment"
 },
 "product_lock": {
 "rule": "The start and end reference show the SAME physical upper garment on the SAME model. Match color, cut, fabric, texture, print, logo and construction exactly to both references in every shot, including the close-up shot which is the same front-facing garment at a nearer framing -- never invent new detail that isn't visible in start_image. Fabric coloring stays perfectly even, no blotches or discoloration.",
 "primary_product": "upper garment — always the dominant commercial focus. Lower garments/shoes are styling context only."
 },
 "camera_and_environment": {
 "camera": "fixed studio position, no zoom/pan/tilt/dolly/tracking in any shot",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting throughout",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout all 3 shots",
 "expression": "relaxed, confident, subtle natural smile, direct eye contact when face is visible",
 "feet_rule": "both feet fully flat on the ground at all times — no tiptoes, no heel lifting",
 "movement_rule": "only the choreography defined per shot — no improvised movement, no walking"
 },
 "aesthetic_direction": "Elevated editorial e-commerce fashion mood. Fabric drapes softly and catches light naturally, emphasizing premium tactile material quality, especially in the close-up.",
 "shots": [
 {
 "id": "shot_01_front_full_body",
 "reference": "start_image",
 "duration_seconds": 3.33,
 "view": "direct front, full body, both shoes visible, model centered",
 "framing": "headroom fixed: crown of head to top of frame = one head-height",
 "choreography": "model holds a relaxed front-facing stance matching start_image exactly, subtle natural weight sway, direct eye contact"
 },
 {
 "id": "shot_02_upper_garment_closeup",
 "reference": "start_image",
 "duration_seconds": 3.33,
 "view": "hard cut to a static close framing on the SAME front-facing upper garment — no camera movement, direct cut only",
 "framing": "tight static crop from chest to waist, fabric/texture/print of the upper garment clearly visible and sharp",
 "choreography": "model holds the pose steady, only extremely subtle natural breathing motion, no repositioning"
 },
 {
 "id": "shot_03_back_view",
 "reference": "end_image",
 "duration_seconds": 3.34,
 "view": "hard cut to a direct rear view, full body, matching end_image exactly",
 "framing": "same full-body framing as shot 1, model perfectly centered",
 "choreography": "model holds a relaxed back-facing stance matching end_image exactly, subtle natural weight sway"
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking",
 "tiptoes", "heel lifting", "floating feet",
 "garment redesign", "color drift", "logo drift", "invented details",
 "fabric blotches or discoloration",
 "walking", "turning", "spinning", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter",
 "children", "minors", "nudity", "exposed intimate areas", "weapons", "violence",
 "political symbols", "religious imagery", "drug use", "hate symbols"
 ]
}"""

KLING_UNTERTEIL_PROMPT = r"""{
 "campaign": "zalando_lower_garment_video_kling",
 "platform_context": "Zalando Product Detail Page (PDP) video",
 "zalando_compliance": {
 "file_format": "MP4, H.264 codec, minimum 24 fps, minimum bitrate 2000 Kb/s, max file size 250MB",
 "resolution_and_ratio": "portrait format, height/width ratio between 1.44 and 1.8, minimum 762x1100px -- 1080x1920 (9:16, ratio 1.778) is within this range and is the actual output resolution",
 "duration_note": "Zalando recommends ~15s (comfort range 12-18s) as guidance, not a hard requirement -- this campaign intentionally keeps the shorter duration set below",
 "content_restrictions": "no minors/children anywhere in frame, no nudity or exposed intimate areas, no violence or weapons, no discriminatory/political/religious content, no substance use, no on-screen text or sound"
 },
 "video_spec": {
 "aspect_ratio": "9:16",
 "fps": 24,
 "duration_seconds": 10,
 "shot_count": 3,
 "shot_duration_seconds": 3.33,
 "editing": "hard cuts only, no transitions, no camera movement of any kind",
 "audio_text_graphics": "none"
 },
 "reference_images": {
 "start_image": "full body, front view — defines silhouette, proportions, overall color, model appearance, lower garment",
 "end_image": "full body, back view — defines rear construction, rear pockets, back print/label, lower garment"
 },
 "product_lock": {
 "rule": "The start and end reference show the SAME physical lower garment on the SAME model. Match color, cut, fabric, texture, print, logo, waistband, pockets and construction exactly to both references in every shot, including the close-up shot which is the same front-facing garment at a nearer framing -- never invent new detail that isn't visible in start_image. Fabric coloring stays perfectly even, no blotches or discoloration.",
 "primary_product": "lower garment — always the dominant commercial focus. Upper garments/shoes are styling context only."
 },
 "camera_and_environment": {
 "camera": "fixed studio position, no zoom/pan/tilt/dolly/tracking in any shot",
 "background": "seamless light-grey studio backdrop",
 "lighting": "soft, even, consistent professional studio lighting throughout",
 "floor_shadow": "subtle natural contact shadow"
 },
 "model": {
 "identity": "same adult model throughout all 3 shots",
 "expression": "relaxed, confident, subtle natural smile, direct eye contact when face is visible",
 "feet_rule": "both feet fully flat on the ground at all times — no tiptoes, no heel lifting",
 "movement_rule": "only the choreography defined per shot — no improvised movement, no walking"
 },
 "aesthetic_direction": "Elevated editorial e-commerce fashion mood. Fabric drapes naturally and moves with the body, emphasizing premium tactile material quality and fit, especially in the close-up.",
 "shots": [
 {
 "id": "shot_01_front_full_body",
 "reference": "start_image",
 "duration_seconds": 3.33,
 "view": "direct front, full body, both shoes visible, model centered",
 "framing": "headroom fixed: crown of head to top of frame = one head-height",
 "choreography": "model holds a relaxed front-facing stance matching start_image exactly, subtle natural weight sway, direct eye contact"
 },
 {
 "id": "shot_02_lower_garment_closeup",
 "reference": "start_image",
 "duration_seconds": 3.33,
 "view": "hard cut to a static close framing on the SAME front-facing lower garment — no camera movement, direct cut only",
 "framing": "tight static crop from waist to knee, fabric/texture/waistband/print of the lower garment clearly visible and sharp",
 "choreography": "model holds the pose steady, only extremely subtle natural breathing motion, no repositioning"
 },
 {
 "id": "shot_03_back_view",
 "reference": "end_image",
 "duration_seconds": 3.34,
 "view": "hard cut to a direct rear view, full body, matching end_image exactly",
 "framing": "same full-body framing as shot 1, model perfectly centered",
 "choreography": "model holds a relaxed back-facing stance matching end_image exactly, subtle natural weight sway"
 }
 ],
 "negative_prompt": [
 "camera movement", "zoom", "pan", "tilt", "tracking",
 "tiptoes", "heel lifting", "floating feet",
 "garment redesign", "color drift", "logo drift", "invented details",
 "fabric blotches or discoloration",
 "walking", "turning", "spinning", "exaggerated or sensual movement",
 "extra limbs", "anatomical distortion",
 "text", "watermarks", "background objects", "additional people",
 "cartoon or CGI appearance", "beauty filter",
 "children", "minors", "nudity", "exposed intimate areas", "weapons", "violence",
 "political symbols", "religious imagery", "drug use", "hate symbols"
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

    now = datetime.now(timezone.utc).isoformat()
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
