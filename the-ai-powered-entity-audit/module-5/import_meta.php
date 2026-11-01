<?php
/**
 * Practical 5.2 — import approved meta descriptions into Rank Math (or Yoast).
 *   wp eval-file import_meta.php approved.csv            # dry run: prints what would change
 *   wp eval-file import_meta.php approved.csv apply      # writes, and keeps the old value
 * approved.csv = review.csv filtered to decision = approve (or edit, with your edit in "new").
 */
$file  = $args[0] ?? 'approved.csv';
$apply = in_array( 'apply', $args, true );
$key   = defined( 'WPSEO_VERSION' ) ? '_yoast_wpseo_metadesc' : 'rank_math_description';
$fh    = fopen( $file, 'r' );
$head  = fgetcsv( $fh );
while ( ( $row = fgetcsv( $fh ) ) !== false ) {
	$r  = array_combine( $head, $row );
	$id = url_to_postid( $r['url'] );
	if ( ! $id ) { WP_CLI::warning( "no post for {$r['url']}" ); continue; }
	$old = get_post_meta( $id, $key, true );
	WP_CLI::log( "#$id  " . ( $apply ? 'UPDATED' : 'would update' ) . "  {$r['url']}" );
	if ( $apply ) {
		update_post_meta( $id, '_mlf_meta_backup', $old );   // the way back
		update_post_meta( $id, $key, wp_slash( $r['new'] ) );
	}
}
