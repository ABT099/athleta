FROM php:8.1-apache

# gd: muscle image compositing. rdkafka: the Kafka consumer/producer (worker).
# $PHPIZE_DEPS + librdkafka-dev are build-time deps for pecl install rdkafka.
RUN apt-get update && apt-get install -y \
        $PHPIZE_DEPS \
        libpng-dev \
        unzip \
        librdkafka-dev \
    && docker-php-ext-install gd \
    && pecl install rdkafka \
    && docker-php-ext-enable rdkafka \
    && rm -rf /var/lib/apt/lists/*

RUN a2enmod rewrite

# Install Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

WORKDIR /var/www/html

# Copy composer files first for better caching
COPY composer.json composer.lock* ./

# Install PHP dependencies
RUN composer install --no-dev --optimize-autoloader --no-interaction || true

# Copy rest of application
COPY . .

RUN chown -R www-data:www-data /var/www/html

EXPOSE 80

CMD ["apache2-foreground"]

