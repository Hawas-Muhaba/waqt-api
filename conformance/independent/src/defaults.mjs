// defaults.mjs -- CAL-012: when a request omits the provider, the provider is `umm-al-qura`.
// Stated here independently (this implementation never imports the reference); tests/test_default_provider_single_source.py
// and conformance vectors for CAL-012 fail if the two ever disagree.
export const DEFAULT_PROVIDER = 'umm-al-qura';
