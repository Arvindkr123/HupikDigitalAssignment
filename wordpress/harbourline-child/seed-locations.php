<?php
/**
 * Run after activating Harbourline Locations:
 * wp eval-file wp-content/themes/harbourline-child/seed-locations.php
 */

$locations = array(
	array(
		'slug'           => 'chatswood',
		'title'          => 'Harbourline Physio - Chatswood',
		'street_address' => 'Level 2, 10 Example Street',
		'suburb'         => 'Chatswood',
		'postcode'       => '2067',
		'phone'          => '02 5550 0101',
		'weekday_open'   => '07:00',
		'weekday_close'  => '19:00',
		'saturday_open'  => '08:00',
		'saturday_close' => '13:00',
		'services'       => "Sports injury\nBack and neck pain\nPost-surgery rehabilitation\nDry needling",
		'faqs'           => array(
			array(
				'question' => 'Where is Harbourline Physio in Chatswood?',
				'answer'   => 'The clinic is at Level 2, 10 Example Street, Chatswood NSW 2067.',
			),
			array(
				'question' => 'When is the Chatswood clinic open?',
				'answer'   => 'We are open Monday to Friday from 7 am to 7 pm, and Saturday from 8 am to 1 pm.',
			),
			array(
				'question' => 'How can I book a Chatswood appointment?',
				'answer'   => 'Call the Chatswood clinic on 02 5550 0101 to arrange an appointment.',
			),
		),
	),
	array(
		'slug'           => 'parramatta',
		'title'          => 'Harbourline Physio - Parramatta',
		'street_address' => '45 Sample Road',
		'suburb'         => 'Parramatta',
		'postcode'       => '2150',
		'phone'          => '02 5550 0202',
		'weekday_open'   => '08:00',
		'weekday_close'  => '18:00',
		'services'       => "Sports injury\nBack and neck pain\nWomen's health physiotherapy",
		'faqs'           => array(
			array(
				'question' => 'Where is Harbourline Physio in Parramatta?',
				'answer'   => 'The clinic is at 45 Sample Road, Parramatta NSW 2150.',
			),
			array(
				'question' => 'When is the Parramatta clinic open?',
				'answer'   => 'We are open Monday to Friday from 8 am to 6 pm.',
			),
			array(
				'question' => 'How can I book a Parramatta appointment?',
				'answer'   => 'Call the Parramatta clinic on 02 5550 0202 to arrange an appointment.',
			),
		),
	),
);

foreach ( $locations as $location ) {
	$post_id = get_page_by_path( $location['slug'], OBJECT, 'location' );
	$post_id = $post_id ? $post_id->ID : 0;
	$post    = array(
		'ID'          => $post_id,
		'post_type'   => 'location',
		'post_status' => 'publish',
		'post_name'   => $location['slug'],
		'post_title'  => $location['title'],
	);
	$post_id = wp_insert_post( $post, true );
	if ( is_wp_error( $post_id ) ) {
		WP_CLI::error( $post_id->get_error_message() );
	}

	foreach ( $location as $key => $value ) {
		if ( in_array( $key, array( 'slug', 'title' ), true ) ) {
			continue;
		}
		update_post_meta( $post_id, '_hlp_' . $key, $value );
	}
}

WP_CLI::success( 'Chatswood and Parramatta location pages are ready.' );
