<?php
get_header();

while ( have_posts() ) :
	the_post();
	$post_id       = get_the_ID();
	$suburb        = get_post_meta( $post_id, '_hlp_suburb', true );
	$street        = get_post_meta( $post_id, '_hlp_street_address', true );
	$postcode      = get_post_meta( $post_id, '_hlp_postcode', true );
	$phone         = get_post_meta( $post_id, '_hlp_phone', true );
	$phone_href    = hlp_phone_href( $phone );
	$booking_url   = get_post_meta( $post_id, '_hlp_booking_url', true );
	$services_text = get_post_meta( $post_id, '_hlp_services', true );
	$services      = array_filter( array_map( 'trim', explode( "\n", $services_text ) ) );
	$faqs          = get_post_meta( $post_id, '_hlp_faqs', true );
	$faqs          = is_array( $faqs ) ? $faqs : array();
	$hours         = array(
		array( 'Monday to Friday', 'weekday_open', 'weekday_close' ),
		array( 'Saturday', 'saturday_open', 'saturday_close' ),
		array( 'Sunday', 'sunday_open', 'sunday_close' ),
	);
	?>
	<main id="main-content" class="hlp-location">
		<article <?php post_class(); ?>>
			<h1><?php echo esc_html( 'Harbourline Physio - ' . $suburb ); ?></h1>

			<section aria-labelledby="hlp-contact-heading">
				<h2 id="hlp-contact-heading"><?php esc_html_e( 'Visit and contact us', 'harbourline' ); ?></h2>
				<address>
					<?php echo esc_html( $street . ', ' . $suburb . ' NSW ' . $postcode ); ?>
				</address>
				<?php if ( $phone_href ) : ?>
					<p><?php esc_html_e( 'Phone:', 'harbourline' ); ?>
						<a href="<?php echo esc_attr( $phone_href ); ?>"><?php echo esc_html( $phone ); ?></a>
					</p>
				<?php endif; ?>
				<a class="hlp-book-button" href="<?php echo esc_url( $booking_url ? $booking_url : '#hlp-booking' ); ?>">
					<?php esc_html_e( 'Book now', 'harbourline' ); ?>
				</a>
				<?php if ( ! $booking_url ) : ?>
					<p id="hlp-booking"><?php esc_html_e( 'Call the clinic to arrange your appointment.', 'harbourline' ); ?></p>
				<?php endif; ?>
			</section>

			<section aria-labelledby="hlp-hours-heading">
				<h2 id="hlp-hours-heading"><?php esc_html_e( 'Opening hours', 'harbourline' ); ?></h2>
				<dl>
					<?php foreach ( $hours as $hour ) : ?>
						<?php
						$opens  = get_post_meta( $post_id, '_hlp_' . $hour[1], true );
						$closes = get_post_meta( $post_id, '_hlp_' . $hour[2], true );
						?>
						<?php if ( hlp_format_time( $opens ) && hlp_format_time( $closes ) ) : ?>
							<dt><?php echo esc_html( $hour[0] ); ?></dt>
							<dd><?php echo esc_html( hlp_format_time( $opens ) . '–' . hlp_format_time( $closes ) ); ?></dd>
						<?php elseif ( 'Sunday' === $hour[0] || 'Saturday' === $hour[0] ) : ?>
							<dt><?php echo esc_html( $hour[0] ); ?></dt>
							<dd><?php esc_html_e( 'Closed', 'harbourline' ); ?></dd>
						<?php endif; ?>
					<?php endforeach; ?>
				</dl>
			</section>

			<?php if ( $services ) : ?>
				<section aria-labelledby="hlp-services-heading">
					<h2 id="hlp-services-heading"><?php esc_html_e( 'Services', 'harbourline' ); ?></h2>
					<ul>
						<?php foreach ( $services as $service ) : ?>
							<li><?php echo esc_html( $service ); ?></li>
						<?php endforeach; ?>
					</ul>
				</section>
			<?php endif; ?>

			<?php if ( $faqs ) : ?>
				<section aria-labelledby="hlp-faq-heading">
					<h2 id="hlp-faq-heading"><?php esc_html_e( 'Frequently asked questions', 'harbourline' ); ?></h2>
					<?php foreach ( $faqs as $faq ) : ?>
						<?php if ( ! empty( $faq['question'] ) && ! empty( $faq['answer'] ) ) : ?>
							<details>
								<summary><?php echo esc_html( $faq['question'] ); ?></summary>
								<p><?php echo esc_html( $faq['answer'] ); ?></p>
							</details>
						<?php endif; ?>
					<?php endforeach; ?>
				</section>
			<?php endif; ?>
		</article>
	</main>
	<?php
endwhile;

get_footer();
