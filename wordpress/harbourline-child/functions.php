<?php
/**
 * Harbourline location pages and metadata.
 */

function hlp_register_location_post_type() {
	register_post_type(
		'location',
		array(
			'labels'       => array(
				'name'          => __( 'Locations', 'harbourline' ),
				'singular_name' => __( 'Location', 'harbourline' ),
				'add_new_item'  => __( 'Add Location', 'harbourline' ),
				'edit_item'     => __( 'Edit Location', 'harbourline' ),
			),
			'public'       => true,
			'has_archive'  => false,
			'show_in_rest' => true,
			'menu_icon'    => 'dashicons-location',
			'supports'     => array( 'title' ),
			'rewrite'      => array(
				'slug'       => 'locations',
				'with_front' => false,
			),
		)
	);
}
add_action( 'init', 'hlp_register_location_post_type' );

function hlp_enqueue_location_styles() {
	wp_enqueue_style(
		'harbourline-locations',
		get_stylesheet_uri(),
		array(),
		wp_get_theme()->get( 'Version' )
	);
}
add_action( 'wp_enqueue_scripts', 'hlp_enqueue_location_styles' );

function hlp_location_meta_fields() {
	return array(
		'street_address' => __( 'Street address', 'harbourline' ),
		'suburb'         => __( 'Suburb', 'harbourline' ),
		'postcode'       => __( 'Postcode', 'harbourline' ),
		'phone'          => __( 'Phone', 'harbourline' ),
		'weekday_open'   => __( 'Monday to Friday — opens', 'harbourline' ),
		'weekday_close'  => __( 'Monday to Friday — closes', 'harbourline' ),
		'saturday_open'  => __( 'Saturday — opens (leave blank if closed)', 'harbourline' ),
		'saturday_close' => __( 'Saturday — closes', 'harbourline' ),
		'sunday_open'    => __( 'Sunday — opens (leave blank if closed)', 'harbourline' ),
		'sunday_close'   => __( 'Sunday — closes', 'harbourline' ),
		'services'       => __( 'Services (one per line)', 'harbourline' ),
	);
}

function hlp_add_location_meta_box() {
	add_meta_box(
		'hlp-location-details',
		__( 'Location details', 'harbourline' ),
		'hlp_render_location_meta_box',
		'location',
		'normal',
		'high'
	);
}
add_action( 'add_meta_boxes_location', 'hlp_add_location_meta_box' );

function hlp_render_location_meta_box( $post ) {
	wp_nonce_field( 'hlp_save_location', 'hlp_location_nonce' );
	$fields = hlp_location_meta_fields();

	foreach ( $fields as $key => $label ) {
		$value = get_post_meta( $post->ID, '_hlp_' . $key, true );
		echo '<p><label for="hlp-' . esc_attr( $key ) . '"><strong>' . esc_html( $label ) . '</strong></label><br>';

		if ( 'services' === $key ) {
			echo '<textarea class="widefat" rows="5" id="hlp-' . esc_attr( $key ) . '" name="hlp_location[' . esc_attr( $key ) . ']">' . esc_textarea( $value ) . '</textarea>';
		} elseif ( false !== strpos( $key, '_open' ) || false !== strpos( $key, '_close' ) ) {
			echo '<input type="time" id="hlp-' . esc_attr( $key ) . '" name="hlp_location[' . esc_attr( $key ) . ']" value="' . esc_attr( $value ) . '">';
		} else {
			echo '<input class="widefat" type="text" id="hlp-' . esc_attr( $key ) . '" name="hlp_location[' . esc_attr( $key ) . ']" value="' . esc_attr( $value ) . '">';
		}
		echo '</p>';
	}

	$booking_url = get_post_meta( $post->ID, '_hlp_booking_url', true );
	echo '<p><label for="hlp-booking-url"><strong>' . esc_html__( 'Booking URL (optional)', 'harbourline' ) . '</strong></label>';
	echo '<input class="widefat" type="url" id="hlp-booking-url" name="hlp_location[booking_url]" value="' . esc_attr( $booking_url ) . '"></p>';

	$faqs = get_post_meta( $post->ID, '_hlp_faqs', true );
	$faqs = is_array( $faqs ) ? $faqs : array();
	echo '<h3>' . esc_html__( 'Frequently asked questions', 'harbourline' ) . '</h3>';
	for ( $index = 0; $index < 3; $index++ ) {
		$question = isset( $faqs[ $index ]['question'] ) ? $faqs[ $index ]['question'] : '';
		$answer   = isset( $faqs[ $index ]['answer'] ) ? $faqs[ $index ]['answer'] : '';
		echo '<p><label for="hlp-faq-question-' . esc_attr( $index ) . '"><strong>' . sprintf( esc_html__( 'Question %d', 'harbourline' ), esc_html( $index + 1 ) ) . '</strong></label>';
		echo '<input class="widefat" id="hlp-faq-question-' . esc_attr( $index ) . '" name="hlp_location[faqs][' . esc_attr( $index ) . '][question]" value="' . esc_attr( $question ) . '"></p>';
		echo '<p><label for="hlp-faq-answer-' . esc_attr( $index ) . '">' . esc_html__( 'Answer', 'harbourline' ) . '</label>';
		echo '<textarea class="widefat" rows="3" id="hlp-faq-answer-' . esc_attr( $index ) . '" name="hlp_location[faqs][' . esc_attr( $index ) . '][answer]">' . esc_textarea( $answer ) . '</textarea></p>';
	}
}

function hlp_sanitize_time( $value ) {
	$value = sanitize_text_field( $value );
	return preg_match( '/^(?:[01]\d|2[0-3]):[0-5]\d$/', $value ) ? $value : '';
}

function hlp_save_location_meta( $post_id ) {
	if ( ! isset( $_POST['hlp_location_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['hlp_location_nonce'] ) ), 'hlp_save_location' ) ) {
		return;
	}
	if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
		return;
	}
	if ( ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	if ( ! isset( $_POST['hlp_location'] ) || ! is_array( $_POST['hlp_location'] ) ) {
		return;
	}

	$values = wp_unslash( $_POST['hlp_location'] );
	foreach ( hlp_location_meta_fields() as $key => $label ) {
		if ( ! isset( $values[ $key ] ) ) {
			continue;
		}
		if ( ! is_scalar( $values[ $key ] ) ) {
			continue;
		}
		$value = 'services' === $key ? sanitize_textarea_field( $values[ $key ] ) : sanitize_text_field( $values[ $key ] );
		if ( false !== strpos( $key, '_open' ) || false !== strpos( $key, '_close' ) ) {
			$value = hlp_sanitize_time( $value );
		}
		update_post_meta( $post_id, '_hlp_' . $key, $value );
	}

	if ( isset( $values['booking_url'] ) && is_scalar( $values['booking_url'] ) ) {
		update_post_meta( $post_id, '_hlp_booking_url', esc_url_raw( $values['booking_url'] ) );
	}

	$faqs = array();
	if ( isset( $values['faqs'] ) && is_array( $values['faqs'] ) ) {
		foreach ( array_slice( $values['faqs'], 0, 3 ) as $faq ) {
			$question = isset( $faq['question'] ) && is_scalar( $faq['question'] ) ? sanitize_text_field( $faq['question'] ) : '';
			$answer   = isset( $faq['answer'] ) && is_scalar( $faq['answer'] ) ? sanitize_textarea_field( $faq['answer'] ) : '';
			if ( '' !== $question && '' !== $answer ) {
				$faqs[] = array(
					'question' => $question,
					'answer'   => $answer,
				);
			}
		}
	}
	update_post_meta( $post_id, '_hlp_faqs', $faqs );
}
add_action( 'save_post_location', 'hlp_save_location_meta' );

function hlp_format_time( $time ) {
	if ( ! preg_match( '/^(?:[01]\d|2[0-3]):[0-5]\d$/', (string) $time ) ) {
		return '';
	}
	$date = DateTime::createFromFormat( '!H:i', $time );
	return $date ? strtolower( $date->format( 'g:i a' ) ) : '';
}

function hlp_hours_schema( $post_id ) {
	$hours = array();
	$sets  = array(
		array( array( 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday' ), 'weekday_open', 'weekday_close' ),
		array( array( 'Saturday' ), 'saturday_open', 'saturday_close' ),
		array( array( 'Sunday' ), 'sunday_open', 'sunday_close' ),
	);
	foreach ( $sets as $set ) {
		$opens  = get_post_meta( $post_id, '_hlp_' . $set[1], true );
		$closes = get_post_meta( $post_id, '_hlp_' . $set[2], true );
		if ( hlp_format_time( $opens ) && hlp_format_time( $closes ) ) {
			$hours[] = array(
				'@type'     => 'OpeningHoursSpecification',
				'dayOfWeek' => $set[0],
				'opens'     => $opens,
				'closes'    => $closes,
			);
		}
	}
	return $hours;
}

function hlp_phone_href( $phone ) {
	$digits = preg_replace( '/\D+/', '', (string) $phone );
	if ( 0 === strpos( $digits, '0' ) ) {
		$digits = '61' . substr( $digits, 1 );
	}
	return '' !== $digits ? 'tel:+' . $digits : '';
}

function hlp_location_schema() {
	if ( ! is_singular( 'location' ) ) {
		return;
	}
	$post_id = get_queried_object_id();
	$phone   = get_post_meta( $post_id, '_hlp_phone', true );
	$address = array(
		'@type'           => 'PostalAddress',
		'streetAddress'   => get_post_meta( $post_id, '_hlp_street_address', true ),
		'addressLocality' => get_post_meta( $post_id, '_hlp_suburb', true ),
		'addressRegion'   => 'NSW',
		'postalCode'      => get_post_meta( $post_id, '_hlp_postcode', true ),
		'addressCountry'  => 'AU',
	);
	$business = array(
		'@context'                => 'https://schema.org',
		'@type'                   => 'MedicalBusiness',
		'name'                    => 'Harbourline Physio - ' . get_post_meta( $post_id, '_hlp_suburb', true ),
		'url'                     => get_permalink( $post_id ),
		'telephone'               => hlp_phone_href( $phone ) ? substr( hlp_phone_href( $phone ), 4 ) : $phone,
		'address'                 => $address,
		'medicalSpecialty'        => 'https://schema.org/Physiotherapy',
		'openingHoursSpecification' => hlp_hours_schema( $post_id ),
	);
	$faqs = get_post_meta( $post_id, '_hlp_faqs', true );
	$faq_entities = array();
	if ( is_array( $faqs ) ) {
		foreach ( $faqs as $faq ) {
			if ( ! empty( $faq['question'] ) && ! empty( $faq['answer'] ) ) {
				$faq_entities[] = array(
					'@type'          => 'Question',
					'name'           => $faq['question'],
					'acceptedAnswer' => array(
						'@type' => 'Answer',
						'text'  => $faq['answer'],
					),
				);
			}
		}
	}

	$entities = array( $business );
	if ( $faq_entities ) {
		$entities[] = array(
			'@context'   => 'https://schema.org',
			'@type'      => 'FAQPage',
			'mainEntity' => $faq_entities,
		);
	}
	echo '<script type="application/ld+json">' . wp_json_encode( $entities, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT ) . '</script>' . "\n";
}
add_action( 'wp_head', 'hlp_location_schema', 20 );
