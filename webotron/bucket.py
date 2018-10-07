#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Classes for S3 buckets."""

from pathlib import Path
import mimetypes

from botocore.exceptions import ClientError

import util


class BucketManager():
    """Manage an S3 bucket."""

    def __init__(self, session):
        """Create a BucketManager object."""
        self.session = session
        self.s3 = self.session.resource('s3')

    def get_region_name(self, bucket):
        """Get the region name of a bucket."""
        client = self.s3.meta.client
        bucket_location = client.get_bucket_location(Bucket=bucket.name)

        return bucket_location['LocationConstraint'] or 'us-east-1'

    def get_bucket_url(self, bucket):
        """Get the website URL for this bucket."""
        region = self.get_region_name(bucket)
        host = util.get_endpoint(region).host
        return "http://{}.{}".format(bucket.name, host)

    def all_buckets(self):
        """Get an iterator for all buckets."""
        return self.s3.buckets.all()

    def all_objects(self, bucket_name):
        """Get an iterator for all objects in a bucket."""
        return self.s3.Bucket(bucket_name).objects.all()

    def init_bucket(self, bucket_name):
        """Create and configure a S3 bucket."""
        bucket = None
        try:
            bucket = self.s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={
                    'LocationConstraint': self.session.region_name
                })
        except ClientError as error:
            if error.response['Error']['Code'] == 'BucketAlreadyOwnedByYou':
                bucket = self.s3.Bucket(bucket_name)
            else:
                raise error

        return bucket

    @staticmethod
    def set_policy(bucket):
        """Set bucket policy to be readable by everyone."""
        policy = """
        {
            "Version":"2012-10-17",
            "Statement":[{
            "Sid":"PublicReadForGetBucketObjects",
            "Effect":"Allow",
            "Principal": "*",
            "Action":["s3:GetObject"],
            "Resource":["arn:aws:s3:::%s/*"]
          }]
        }
        """ % bucket.name
        policy = policy.strip()

        pol = bucket.Policy()
        pol.put(Policy=policy)

    @staticmethod
    def configure_website(bucket):
        """Set bucket settings to be able to serve a static website."""
        web = bucket.Website()
        web.put(
            WebsiteConfiguration={
                'ErrorDocument': {
                    'Key': 'error.html'
                },
                'IndexDocument': {
                    'Suffix': 'index.html'
                }
            })

    @staticmethod
    def upload_file(bucket, path, key):
        """Upload path to s3 bucket."""
        content_type = mimetypes.guess_type(key)[0] or 'text/plain'

        return bucket.upload_file(
            path,
            key,
            ExtraArgs={
                'ContentType': content_type
            })

    def sync(self, pathname, bucket_name):
        """Sync the pathname tree with bucket_name."""
        bucket = self.s3.Bucket(bucket_name)
        root = Path(pathname).expanduser().resolve()

        def handle_directory(target):
            for a_path in target.iterdir():
                if a_path.is_dir():
                    handle_directory(a_path)
                if a_path.is_file():
                    self.upload_file(
                        bucket,
                        str(a_path),
                        str(a_path.relative_to(root))
                    )
        handle_directory(root)
