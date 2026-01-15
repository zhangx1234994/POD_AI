import uploadConstants from './upload';
import taskConstants from './task';
import userConstants from './user';
import galleryConstants from './gallery';
import optionsConstants from './options';
import imageConstants from './image';
import metadataConstants from './metadata';
import errorMessagesConstants from './errorMessages';

export * from './upload';
export * from './task';
export * from './user';
export * from './gallery';
export * from './options';
export * from './image';
export * from './metadata';
export * from './errorMessages';

export {
    uploadConstants,
    taskConstants,
    userConstants,
    galleryConstants,
    optionsConstants,
    imageConstants,
    metadataConstants,
    errorMessagesConstants,
};

export default {
  ...uploadConstants,
  ...taskConstants,
  ...userConstants,
  ...galleryConstants,
  ...optionsConstants,
  ...imageConstants,
  ...metadataConstants,
  ...errorMessagesConstants,
};
