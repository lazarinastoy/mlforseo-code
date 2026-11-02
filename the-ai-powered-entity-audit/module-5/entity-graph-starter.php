<?php
/**
 * Plugin Name: Entity Graph (starter)
 * Description: One owned JSON-LD graph per page, rendered from an entity registry plus live WordPress data. The Entity Audit course, Lesson 5.6.
 * Version: 1.0.0
 *
 * This is the pattern behind the structured data on mlforseo.com and lazarinastoy.com, cut down to
 * a starter you can read in ten minutes and extend with Claude Code:
 *
 *   registry.json  holds only the facts WordPress doesn't have: who the organisation is, who the
 *                  people are, their @ids and sameAs. Edit it, never the output.
 *   live data      everything else (titles, dates, authors, excerpts, images) is read from the
 *                  same fields the page renders, so the markup can't drift from the page.
 *   router         picks a builder for the page type; each builder returns nodes.
 *   finalize       drops empty values, merges nodes that share an @id (first definition wins)
 *                  and prints exactly ONE <script type="application/ld+json">.
 *
 * Install: put this file and registry.json in wp-content/mu-plugins/entity-graph/ and load it from
 * a one-line mu-plugin (require __DIR__ . '/entity-graph/entity-graph-starter.php';), or install it
 * as a regular plugin. Then switch your SEO plugin's schema output off (below does it for the
 * common ones) and run graph_check.py: every page should have exactly one ld+json block.
 * Kill switch: define( 'ENTITY_GRAPH_OFF', true ); in wp-config.php.
 */

if ( ! defined( 'ABSPATH' ) || ( defined( 'ENTITY_GRAPH_OFF' ) && ENTITY_GRAPH_OFF ) ) {
	return;
}

const EG_VERSION = '1.0.0';

/** The registry, read once per request. */
function eg_registry() {
	static $reg = null;
	if ( null === $reg ) {
		$file = __DIR__ . '/registry.json';
		$reg  = is_readable( $file ) ? json_decode( (string) file_get_contents( $file ), true ) : [];
		$reg  = is_array( $reg ) ? $reg : [];
	}
	return $reg;
}

/** Registry nodes by @id, and the ones this site owns (their @id is on this host). */
function eg_entities( $owned_only = false ) {
	$host = wp_parse_url( home_url(), PHP_URL_HOST );
	$out  = [];
	foreach ( eg_registry()['entities'] ?? [] as $e ) {
		if ( empty( $e['@id'] ) ) {
			continue;
		}
		if ( $owned_only && wp_parse_url( $e['@id'], PHP_URL_HOST ) !== $host ) {
			continue;
		}
		$out[ $e['@id'] ] = $e;
	}
	return $out;
}

function eg_ref( $id ) {
	return $id ? [ '@id' => $id ] : null;
}

/** The registry node of a given type that this site owns, e.g. its Organization or WebSite. */
function eg_site_id( $type ) {
	foreach ( eg_entities( true ) as $id => $e ) {
		if ( ( $e['@type'] ?? '' ) === $type ) {
			return $id;
		}
	}
	return null;
}

/** A WordPress user -> their registry @id ("authors": {"login": "@id"}), else a local Person. */
function eg_author( $user_id ) {
	$u = get_userdata( $user_id );
	if ( ! $u ) {
		return [ null, [] ];
	}
	$map = eg_registry()['authors'] ?? [];
	if ( ! empty( $map[ $u->user_login ] ) ) {
		return [ $map[ $u->user_login ], [] ];            // the canonical node lives in the registry
	}
	$id = get_author_posts_url( $user_id ) . '#person';
	return [ $id, [ [ '@type' => 'Person', '@id' => $id, 'name' => $u->display_name, 'url' => get_author_posts_url( $user_id ) ] ] ];
}

function eg_webpage( $url, $name, $type = 'WebPage', $extra = [] ) {
	return array_merge( [
		'@type'      => $type,
		'@id'        => $url . '#webpage',
		'url'        => $url,
		'name'       => wp_strip_all_tags( html_entity_decode( $name, ENT_QUOTES ) ),
		'isPartOf'   => eg_ref( eg_site_id( 'WebSite' ) ),
		'breadcrumb' => eg_ref( $url . '#breadcrumb' ),
		'inLanguage' => get_bloginfo( 'language' ),
	], $extra );
}

function eg_breadcrumb( $url, $trail ) {
	$items = [];
	foreach ( array_values( $trail ) as $i => $t ) {
		$items[] = [ '@type' => 'ListItem', 'position' => $i + 1, 'name' => $t[0], 'item' => $t[1] ];
	}
	return [ '@type' => 'BreadcrumbList', '@id' => $url . '#breadcrumb', 'itemListElement' => $items ];
}

/* ── Builders: one per page type. Add yours here (Course, Product, Event, DefinedTerm…). ── */

function eg_build_home() {
	$url = home_url( '/' );
	return [ eg_webpage( $url, get_bloginfo( 'name' ), 'WebPage', [ 'about' => eg_ref( eg_site_id( 'Organization' ) ), 'breadcrumb' => null ] ) ];
}

function eg_build_post( $post ) {
	$url              = get_permalink( $post );
	[ $author, $more ] = eg_author( $post->post_author );
	$cat              = get_the_category( $post->ID );
	$trail            = [ [ 'Home', home_url( '/' ) ] ];
	if ( $cat ) {
		$trail[] = [ $cat[0]->name, get_category_link( $cat[0] ) ];
	}
	$trail[] = [ get_the_title( $post ), $url ];
	$nodes   = array_merge( $more, [
		eg_webpage( $url, get_the_title( $post ) ),
		eg_breadcrumb( $url, $trail ),
		[
			'@type'            => 'BlogPosting',
			'@id'              => $url . '#article',
			'headline'         => wp_strip_all_tags( get_the_title( $post ) ),
			'description'      => wp_strip_all_tags( get_the_excerpt( $post ) ),
			'datePublished'    => get_post_time( 'c', true, $post ),
			'dateModified'     => get_post_modified_time( 'c', true, $post ),
			'author'           => eg_ref( $author ),
			'publisher'        => eg_ref( eg_site_id( 'Organization' ) ),
			'mainEntityOfPage' => eg_ref( $url . '#webpage' ),
			'image'            => get_the_post_thumbnail_url( $post, 'full' ) ?: null,
			'about'            => eg_about( $url ),
		],
	] );
	return $nodes;
}

function eg_build_page( $post ) {
	$url  = get_permalink( $post );
	$conf = eg_page_conf( $url );
	return [
		eg_webpage( $url, get_the_title( $post ), $conf['type'] ?? 'WebPage', [ 'about' => eg_about( $url ) ] ),
		eg_breadcrumb( $url, [ [ 'Home', home_url( '/' ) ], [ get_the_title( $post ), $url ] ] ),
	];
}

/** "pages": {"/about/": {"type": "AboutPage", "about": "<@id>"}} in the registry. */
function eg_page_conf( $url ) {
	$path = wp_parse_url( $url, PHP_URL_PATH ) ?: '/';
	return eg_registry()['pages'][ trailingslashit( $path ) ] ?? [];
}

function eg_about( $url ) {
	$c = eg_page_conf( $url );
	return empty( $c['about'] ) ? null : eg_ref( $c['about'] );
}

/** Router: which builder runs on this request. Unknown types get a plain WebPage. */
function eg_build() {
	$nodes = array_values( eg_entities( true ) );           // the entities this site owns, in full
	if ( is_front_page() ) {
		$nodes = array_merge( $nodes, eg_build_home() );
	} elseif ( is_singular( 'post' ) ) {
		$nodes = array_merge( $nodes, eg_build_post( get_queried_object() ) );
	} elseif ( is_singular() ) {
		$nodes = array_merge( $nodes, eg_build_page( get_queried_object() ) );
	} else {
		$url     = home_url( add_query_arg( [] ) );
		$nodes[] = eg_webpage( $url, wp_get_document_title(), 'CollectionPage', [ 'breadcrumb' => null ] );
	}
	return eg_finalize( $nodes );
}

/** Drop empty values, merge nodes by @id (first definition wins). */
function eg_finalize( $nodes ) {
	$clean = function ( $v ) use ( &$clean ) {
		if ( ! is_array( $v ) ) {
			return $v;
		}
		$out = [];
		foreach ( $v as $k => $x ) {
			$x = $clean( $x );
			if ( null === $x || '' === $x || [] === $x ) {
				continue;
			}
			$out[ $k ] = $x;
		}
		return $out;
	};
	$by_id = [];
	$rest  = [];
	foreach ( $nodes as $n ) {
		$n = $clean( $n );
		if ( ! $n ) {
			continue;
		}
		if ( empty( $n['@id'] ) ) {
			$rest[] = $n;
		} elseif ( isset( $by_id[ $n['@id'] ] ) ) {
			$by_id[ $n['@id'] ] += $n;                        // first definition wins, gaps filled
		} else {
			$by_id[ $n['@id'] ] = $n;
		}
	}
	return array_merge( array_values( $by_id ), $rest );
}

add_action( 'wp_head', function () {
	if ( is_404() || is_search() || is_feed() ) {
		return;
	}
	$graph = [ '@context' => 'https://schema.org', '@graph' => eg_build() ];
	printf( "<script type=\"application/ld+json\" class=\"entity-graph\" data-v=\"%s\">%s</script>\n",
		esc_attr( EG_VERSION ),
		wp_json_encode( $graph, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) );
}, 20 );

/* ── Owning the graph is mostly switching other emitters off. ── */
add_filter( 'rank_math/json_ld', '__return_empty_array', PHP_INT_MAX );  // Rank Math keeps titles, meta, sitemaps
add_filter( 'wpseo_json_ld_output', '__return_false' );                   // Yoast
add_filter( 'aioseo_schema_disable', '__return_true' );                   // All in One SEO
add_action( 'init', function () {                                         // WooCommerce
	if ( function_exists( 'WC' ) && isset( WC()->structured_data ) ) {
		remove_action( 'wp_footer', [ WC()->structured_data, 'output_structured_data' ], 10 );
	}
} );
add_filter( 'render_block', function ( $html ) {                         // block-level ld+json (FAQ blocks etc.)
	return false === stripos( $html, 'application/ld+json' ) ? $html
		: preg_replace( '#<script[^>]*application/ld\+json[^>]*>.*?</script>#is', '', $html );
} );
